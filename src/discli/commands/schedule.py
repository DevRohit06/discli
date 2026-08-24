"""`discli schedule` — run discli commands on a recurring schedule.

Schedules live in ``~/.discli/schedules.json``. `schedule run` is the process
that actually fires them, built on ``discord.ext.tasks`` for wall-clock
scheduling with timezone support, bounded repeat counts, and automatic
restart with exponential backoff on transient failures.

Security note: an action is a *discli* command line, never a shell command.
It is split with ``shlex`` (so no shell metacharacters, globbing, or command
substitution) and the first token must name a real discli command group, so a
schedules file can only ever invoke discli itself. Actions run through the
same permission profile and audit log as if typed by hand.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import re
import shlex
from pathlib import Path

import click
# discord.py's sentinel for "argument not supplied"; tasks.Loop uses it to
# tell interval scheduling apart from wall-clock scheduling.
from discord.utils import MISSING

from discli.security import audit_log

SCHEDULES_PATH = Path.home() / ".discli" / "schedules.json"

# Interval shorthand: 30s, 15m, 2h, 1d.
_DURATION_RE = re.compile(r"^(\d+)([smhd])$")
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# Loops firing more often than this are almost always a mistake, and Discord
# rate limits will punish them.
MIN_INTERVAL_SECONDS = 30


def load_schedules() -> list[dict]:
    if not SCHEDULES_PATH.exists():
        return []
    try:
        data = json.loads(SCHEDULES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"{SCHEDULES_PATH} is not valid JSON: {exc}")
    schedules = data.get("schedules", []) if isinstance(data, dict) else data
    if not isinstance(schedules, list):
        raise click.ClickException(f"{SCHEDULES_PATH} does not contain a list of schedules.")
    return schedules


def save_schedules(schedules: list[dict]) -> None:
    SCHEDULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULES_PATH.write_text(
        json.dumps({"schedules": schedules}, indent=2) + "\n", encoding="utf-8"
    )


def parse_duration(value: str) -> int:
    match = _DURATION_RE.match(value.strip().lower())
    if not match:
        raise click.ClickException(
            f"Invalid duration: {value!r}. Use a number followed by s, m, h, or d (e.g. 30m)."
        )
    seconds = int(match.group(1)) * _DURATION_UNITS[match.group(2)]
    if seconds < MIN_INTERVAL_SECONDS:
        raise click.ClickException(
            f"Interval must be at least {MIN_INTERVAL_SECONDS}s; got {value}."
        )
    return seconds


def parse_time(value: str, tz: str | None) -> datetime.time:
    try:
        hour_str, minute_str = value.strip().split(":", 1)
        hour, minute = int(hour_str), int(minute_str)
    except ValueError:
        raise click.ClickException(f"Invalid time: {value!r}. Use 24-hour HH:MM (e.g. 09:00).")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise click.ClickException(f"Invalid time: {value!r}. Hours 00-23, minutes 00-59.")

    tzinfo: datetime.tzinfo = datetime.timezone.utc
    if tz:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            tzinfo = ZoneInfo(tz)
        except ZoneInfoNotFoundError:
            raise click.ClickException(
                f"Unknown timezone: {tz!r}. Use an IANA name like 'America/New_York'. "
                "On Windows this also needs the 'tzdata' package installed."
            )
    return datetime.time(hour=hour, minute=minute, tzinfo=tzinfo)


# Tokens that only mean anything to a shell. Actions never touch one, so their
# presence means the author expected shell semantics they will not get --
# `server list && curl x` would otherwise be accepted here and then fail at fire
# time with "&&" passed as a literal argument.
#
# Matched as whole tokens, which is why parse_action lexes with
# punctuation_chars. Backticks and $ are deliberately absent: no shell is
# involved so they cannot do anything, and rejecting them would break
# `message send <ch> "run \`npm test\`"` -- code formatting is ordinary Discord
# message content. `$(...)` is still caught, via its parenthesis.
_SHELL_OPERATORS = {"&&", "||", "|", ";", "&", ">", ">>", "<", "<<", "(", ")"}

# Commands that never terminate, so they can never complete one scheduled run.
_NON_TERMINATING = {"serve", "listen", "schedule"}


def parse_action(action: str) -> list[str]:
    """Split a discli command line and validate it against the command tree.

    Uses shlex rather than a shell, so quoting works but metacharacters,
    globbing, and command substitution do not. Walking the real Click tree
    means a schedules file can only ever invoke discli, and that typos are
    caught when the schedule is added rather than at 3am when it fires.
    """
    # punctuation_chars makes shlex emit ; && | < > as their own tokens.
    # Plain shlex.split() would fold them into neighbours ("list;"), so the
    # operator check below would miss them and the error would come out as a
    # confusing "unknown command 'list;'" instead of saying what is wrong.
    try:
        lexer = shlex.shlex(action, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        argv = list(lexer)
    except ValueError as exc:
        raise click.ClickException(f"Could not parse action {action!r}: {exc}")
    if not argv:
        raise click.ClickException("Action is empty.")

    if argv[0] == "discli":
        argv = argv[1:]
    if not argv:
        raise click.ClickException("Action is empty.")

    shell_tokens = [t for t in argv if t in _SHELL_OPERATORS]
    if shell_tokens:
        raise click.ClickException(
            f"Actions do not run through a shell, so {shell_tokens[0]!r} would be passed "
            "as a literal argument. Use one discli command per schedule."
        )

    if argv[0] in _NON_TERMINATING:
        raise click.ClickException(
            f"'{argv[0]}' runs indefinitely and cannot be used as a scheduled action."
        )

    from discli.cli import main

    node = main
    consumed = 0
    while isinstance(node, click.Group) and consumed < len(argv):
        token = argv[consumed]
        if token.startswith("-"):
            break
        # Click's stock Group.get_command ignores its ctx argument, so reading
        # .commands directly avoids fabricating one.
        child = node.commands.get(token)
        if child is None:
            path = "discli " + " ".join(argv[:consumed]) if consumed else "discli"
            raise click.ClickException(
                f"Unknown command {token!r} for '{path.strip()}'. "
                f"Available: {', '.join(sorted(node.commands))}"
            )
        node = child
        consumed += 1

    return argv


def _find(schedules: list[dict], name: str) -> dict:
    for entry in schedules:
        if entry.get("name") == name:
            return entry
    raise click.ClickException(f"No schedule named {name!r}. Run 'discli schedule list'.")


def run_action(argv: list[str]) -> tuple[bool, str]:
    """Invoke a discli command in-process. Returns (ok, detail).

    Called from a worker thread, never the scheduler's event loop: discli
    commands call asyncio.run() internally, which raises if a loop is already
    running on that thread. A fresh thread gets a fresh loop.
    """
    from discli.cli import main

    try:
        main.main(args=argv, standalone_mode=False)
        return True, "ok"
    except click.ClickException as exc:
        return False, exc.format_message()
    except SystemExit as exc:
        code = exc.code or 0
        return code == 0, f"exit code {code}"
    except Exception as exc:  # noqa: BLE001 - a failing action must not kill the scheduler
        return False, f"{type(exc).__name__}: {exc}"


def _describe(entry: dict) -> str:
    if entry.get("time"):
        when = f"daily at {entry['time']} {entry.get('tz') or 'UTC'}"
    else:
        when = f"every {entry.get('every_human') or str(entry.get('every')) + 's'}"
    state = "" if entry.get("enabled", True) else " [disabled]"
    last = entry.get("last_run")
    tail = f" (last run {last[:19].replace('T', ' ')}: {entry.get('last_result')})" if last else ""
    return f"{entry['name']}{state} — {when} — {entry['action']}{tail}"


@click.group("schedule")
def schedule_group():
    """Run discli commands on a recurring schedule."""


@schedule_group.command("add")
@click.argument("name")
@click.option("--action", required=True, help="discli command to run, e.g. 'message send 123 \"hi\"'.")
@click.option("--time", "at_time", default=None, help="Daily wall-clock time, 24-hour HH:MM.")
@click.option("--tz", default=None, help="IANA timezone for --time (default UTC), e.g. America/New_York.")
@click.option("--every", default=None, help="Interval instead of a fixed time: 30s, 15m, 2h, 1d.")
@click.option("--count", default=None, type=int, help="Stop after this many runs (default: unlimited).")
@click.option("--force", is_flag=True, default=False, help="Overwrite an existing schedule with this name.")
@click.pass_context
def schedule_add(ctx, name, action, at_time, tz, every, count, force):
    """Add a schedule. Give either --time or --every."""
    from discli.utils import output

    if bool(at_time) == bool(every):
        raise click.ClickException("Give exactly one of --time or --every.")
    if tz and not at_time:
        raise click.ClickException("--tz only applies to --time.")
    if count is not None and count < 1:
        raise click.ClickException("--count must be at least 1.")

    argv = parse_action(action)
    entry = {
        "name": name,
        "action": action,
        "argv": argv,
        "enabled": True,
        "count": count,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "last_run": None,
        "last_result": None,
    }
    if at_time:
        parse_time(at_time, tz)  # validate now rather than at run time
        entry["time"] = at_time
        entry["tz"] = tz
    else:
        entry["every"] = parse_duration(every)
        entry["every_human"] = every

    schedules = load_schedules()
    existing = next((s for s in schedules if s.get("name") == name), None)
    if existing is not None:
        if not force:
            raise click.ClickException(f"A schedule named {name!r} already exists. Use --force to replace it.")
        schedules[schedules.index(existing)] = entry
    else:
        schedules.append(entry)
    save_schedules(schedules)
    audit_log("schedule add", {"name": name, "action": action})
    output(ctx, entry, plain_text=f"Added schedule: {_describe(entry)}")


@schedule_group.command("list")
@click.pass_context
def schedule_list(ctx):
    """List configured schedules."""
    from discli.utils import output

    schedules = load_schedules()
    plain = "\n".join(_describe(s) for s in schedules) if schedules else "No schedules configured."
    output(ctx, schedules, plain_text=plain)


@schedule_group.command("remove")
@click.argument("name")
@click.pass_context
def schedule_remove(ctx, name):
    """Remove a schedule."""
    from discli.security import confirm_destructive
    from discli.utils import output

    confirm_destructive("schedule remove", name)
    schedules = load_schedules()
    entry = _find(schedules, name)
    schedules.remove(entry)
    save_schedules(schedules)
    audit_log("schedule remove", {"name": name})
    output(ctx, {"name": name, "removed": True}, plain_text=f"Removed schedule {name!r}")


@schedule_group.command("run-now")
@click.argument("name")
@click.pass_context
def schedule_run_now(ctx, name):
    """Run a schedule's action once, immediately."""
    from discli.utils import output

    schedules = load_schedules()
    entry = _find(schedules, name)
    argv = entry.get("argv") or parse_action(entry["action"])

    ok, detail = run_action(argv)
    entry["last_run"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry["last_result"] = "ok" if ok else f"failed: {detail}"
    save_schedules(schedules)
    audit_log("schedule run-now", {"name": name, "result": entry["last_result"]})

    output(ctx, {"name": name, "ok": ok, "detail": detail},
           plain_text=f"{name}: {'ok' if ok else 'failed — ' + detail}")
    if not ok:
        ctx.exit(1)


@schedule_group.command("run")
@click.option("--name", "names", multiple=True, help="Only run these schedules (repeatable).")
@click.pass_context
def schedule_run(ctx, names):
    """Run the scheduler in the foreground until interrupted.

    Each schedule becomes a discord.ext.tasks loop, so wall-clock times honour
    their timezone, --count is respected, and transient failures retry with
    exponential backoff instead of killing the schedule.
    """
    from discord.ext import tasks

    schedules = [s for s in load_schedules() if s.get("enabled", True)]
    if names:
        wanted = set(names)
        schedules = [s for s in schedules if s.get("name") in wanted]
        missing = wanted - {s.get("name") for s in schedules}
        if missing:
            raise click.ClickException(f"No enabled schedule named: {', '.join(sorted(missing))}")
    if not schedules:
        raise click.ClickException("No enabled schedules to run. Add one with 'discli schedule add'.")

    def _build(entry: dict):
        argv = entry.get("argv") or parse_action(entry["action"])
        name = entry["name"]

        async def _fire() -> None:
            # discli commands call asyncio.run(); a worker thread gives each
            # one its own event loop instead of colliding with this one.
            ok, detail = await asyncio.to_thread(run_action, argv)
            stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            status = "ok" if ok else f"failed: {detail}"
            click.echo(f"[{stamp[:19].replace('T', ' ')}] {name}: {status}", err=True)
            audit_log("schedule fire", {"name": name, "result": status})
            # Persist outcome so `schedule list` reflects the last run even
            # after the scheduler stops.
            stored = load_schedules()
            for item in stored:
                if item.get("name") == name:
                    item["last_run"] = stamp
                    item["last_result"] = status
                    break
            save_schedules(stored)

        common = {"count": entry.get("count"), "reconnect": True, "name": f"discli-schedule-{name}"}
        if entry.get("time"):
            loop = tasks.Loop(
                _fire,
                seconds=MISSING,
                minutes=MISSING,
                hours=MISSING,
                time=parse_time(entry["time"], entry.get("tz")),
                **common,
            )
        else:
            loop = tasks.Loop(
                _fire,
                seconds=float(entry["every"]),
                minutes=0,
                hours=0,
                time=MISSING,
                **common,
            )

            @loop.before_loop
            async def _skip_immediate_run() -> None:
                # An interval loop otherwise fires the moment the scheduler
                # starts, which is surprising for "every 6h".
                await asyncio.sleep(float(entry["every"]))

        @loop.error
        async def _on_error(exc: BaseException) -> None:
            click.echo(f"schedule {name!r} stopped: {exc!r}", err=True)
            audit_log("schedule error", {"name": name, "error": repr(exc)}, result="error")

        return loop

    async def _main() -> None:
        loops = [_build(entry) for entry in schedules]
        for loop in loops:
            loop.start()
        click.echo(f"Running {len(loops)} schedule(s). Ctrl-C to stop.", err=True)
        try:
            while any(loop.is_running() for loop in loops):
                await asyncio.sleep(1)
        finally:
            for loop in loops:
                loop.cancel()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        click.echo("Scheduler stopped.", err=True)

