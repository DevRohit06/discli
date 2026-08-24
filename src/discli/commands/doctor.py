"""`discli doctor` — verify the local install can actually do what it claims.

Groups checks into CORE / VOICE / STT / TTS / TOOLS / EXAMPLES. Each check
records (name, ok, detail, hint). Exit code is the number of failed checks,
capped at 1 so CI can treat any failure as a single non-zero. ``--json``
emits machine-readable output for scripting.

A check that depends on an optional extra (voice, STT/TTS providers) reports
"not configured" rather than failing when that extra simply isn't installed —
the goal is to be silent for devs who never touch voice, and explicit only
when something they *did* configure is broken.
"""

from __future__ import annotations

import json as json_mod
import os
import shutil
import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click

from discli.config import load_config


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    hint: str = ""
    skipped: bool = False


@dataclass
class Section:
    name: str
    checks: list[Check] = field(default_factory=list)


def _pkg_version(name: str) -> str | None:
    """Resolve a package version, trying common spelling variants."""
    for candidate in (name, name.replace("-", "_"), name.replace("_", "-"), name.lower()):
        try:
            return version(candidate)
        except PackageNotFoundError:
            continue
    return None


def _voice_extras_installed() -> bool:
    """True if any of the voice optional dependencies is present.

    Used to decide whether the VOICE section reports `[--]` (developer never
    opted in — leave them alone) or runs the full check (developer asked for
    voice but it's not wired correctly).
    """
    return any(
        _pkg_version(p) is not None
        for p in ("PyNaCl", "discord-ext-voice-recv", "davey")
    )


def _check_python() -> Check:
    v = sys.version_info
    ok = v >= (3, 10)
    detail = f"Python {v.major}.{v.minor}.{v.micro}"
    return Check(
        "python",
        ok,
        detail,
        hint="discli requires Python 3.10+" if not ok else "",
    )


def _check_token() -> Check:
    token = os.environ.get("DISCORD_BOT_TOKEN") or load_config().get("token")
    if token:
        return Check("bot token", True, "configured")
    return Check(
        "bot token",
        False,
        "not configured",
        hint="run `discli config set token <TOKEN>` or set DISCORD_BOT_TOKEN",
    )


def _check_discord_py() -> Check:
    v = _pkg_version("discord.py")
    if v is None:
        return Check(
            "discord.py",
            False,
            "not installed",
            hint="reinstall discli — discord.py is a core dep",
        )
    return Check("discord.py", True, f"v{v}")


def _check_opus() -> Check:
    try:
        import discord.opus  # type: ignore[import]
    except Exception as exc:
        return Check("libopus", False, f"import failed: {exc!r}")
    try:
        loaded = discord.opus.is_loaded()
    except Exception as exc:
        return Check("libopus", False, f"is_loaded() failed: {exc!r}")
    if loaded:
        return Check("libopus", True, "loaded")
    return Check(
        "libopus",
        False,
        "not loaded",
        hint="install libopus (apt install libopus0 / brew install opus) and restart",
    )


def _check_pynacl() -> Check:
    v = _pkg_version("PyNaCl")
    if v is None:
        return Check(
            "PyNaCl",
            False,
            "not installed",
            hint="install voice extra: `uv sync --extra voice` (or `pip install discord-cli-agent[voice]`)",
        )
    return Check("PyNaCl", True, f"v{v}")


def _check_voice_recv() -> Check:
    v = _pkg_version("discord-ext-voice-recv") or _pkg_version("discord.ext.voice-recv")
    if v is None:
        return Check(
            "discord-ext-voice-recv",
            False,
            "not installed",
            hint="install voice extra: `uv sync --extra voice`",
        )
    pinned = "0.5.2a179"
    if v != pinned:
        return Check(
            "discord-ext-voice-recv",
            False,
            f"v{v} (expected {pinned})",
            hint=(
                "discli pins this version because newer/older alphas have known "
                "bugs in our flow. Run `uv sync --extra voice` to resolve."
            ),
        )
    return Check("discord-ext-voice-recv", True, f"v{v}")


def _check_davey() -> Check:
    v = _pkg_version("davey")
    if v is None:
        return Check(
            "davey (DAVE crypto)",
            False,
            "not installed",
            hint="install voice extra: `uv sync --extra voice` — DAVE is required for listening",
        )
    return Check("davey (DAVE crypto)", True, f"v{v}")


def _check_dave_patches() -> Check:
    try:
        from discli.voice_engine import install_voice_recv_patches
    except Exception as exc:
        return Check("DAVE/Opus patches", False, f"voice_engine import failed: {exc!r}")
    try:
        installed = install_voice_recv_patches()
    except Exception as exc:
        return Check(
            "DAVE/Opus patches",
            False,
            f"install raised: {exc!r}",
            hint="check that davey and voice_recv versions match what discli expects",
        )
    if installed:
        return Check("DAVE/Opus patches", True, "install ok")
    return Check(
        "DAVE/Opus patches",
        False,
        "skipped — voice_recv or davey missing",
        hint="install voice extra: `uv sync --extra voice`",
    )


def _check_env(var: str, *, friendly: str | None = None) -> Check:
    label = friendly or var
    if os.environ.get(var):
        return Check(label, True, "set")
    return Check(label, False, "not set", hint=f"export {var}=...", skipped=True)


def _check_ffmpeg() -> Check:
    path = shutil.which("ffmpeg")
    if path:
        return Check("ffmpeg", True, path)
    return Check(
        "ffmpeg",
        False,
        "not on PATH",
        hint="install ffmpeg — required for `discli voice play` and TTS playback",
    )


def _voice_section() -> Section:
    """VOICE checks. If no voice extra is installed at all, treat the whole
    section as "not configured" so developers who never touch voice see a
    clean report instead of a wall of red.
    """
    if not _voice_extras_installed():
        return Section(
            "VOICE",
            [
                Check(
                    "voice extras",
                    True,
                    "not configured",
                    hint="install with `uv sync --extra voice` if you want voice features",
                    skipped=True,
                )
            ],
        )
    return Section(
        "VOICE",
        [
            _check_opus(),
            _check_pynacl(),
            _check_voice_recv(),
            _check_davey(),
            _check_dave_patches(),
        ],
    )


def _stt_section() -> Section:
    return Section(
        "STT",
        [
            _check_env("DEEPGRAM_API_KEY"),
            _check_env("OPENAI_API_KEY", friendly="OPENAI_API_KEY (Whisper)"),
        ],
    )


def _tts_section() -> Section:
    return Section(
        "TTS",
        [
            _check_env("ELEVENLABS_API_KEY"),
            _check_env("OPENAI_API_KEY", friendly="OPENAI_API_KEY (TTS)"),
            _check_env("DEEPGRAM_API_KEY", friendly="DEEPGRAM_API_KEY (Aura)"),
        ],
    )


# Permissions Discord carved out of broader ones. A bot invited before the
# split carries the old bit but not the new one, so it silently loses a
# capability it used to have -- an invite-link problem no local check can see.
# (new bit, bit that used to grant it, enforced from, what breaks without it)
PERMISSION_SPLITS = [
    ("pin_messages", "manage_messages", "2026-01", "message pin, message unpin"),
    ("bypass_slowmode", "manage_messages", "2026-02-23", "posting while slowmode is active"),
    ("create_expressions", "manage_expressions", "2026-02-23", "emoji upload"),
    ("create_events", "manage_events", "2026-02-23", "event create"),
]

# Guild permissions discli commands actually depend on, mapped to the commands
# that need them. Used for the informational grant summary.
DISCLI_PERMISSIONS = {
    "view_channel": "channel list, message list",
    "read_message_history": "message history, message search",
    "send_messages": "message send, message reply",
    "embed_links": "message send --embed-*",
    "attach_files": "message send --file",
    "add_reactions": "reaction add",
    "send_polls": "poll create",
    "create_public_threads": "thread create",
    "manage_messages": "message delete, message bulk-delete",
    "pin_messages": "message pin, message unpin",
    "manage_channels": "channel create/delete/edit, invite delete",
    "create_instant_invite": "invite create",
    "manage_roles": "role *, channel set-permissions",
    "manage_nicknames": "member nick",
    "kick_members": "member kick",
    "ban_members": "member ban, member unban",
    "moderate_members": "member timeout",
    "move_members": "voice move",
    "manage_webhooks": "webhook *",
    "manage_guild": "server edit, invite list",
    "view_audit_log": "server audit-log",
    "create_expressions": "emoji upload",
    "manage_expressions": "emoji rename, emoji delete",
    "create_events": "event create",
    "manage_events": "event delete",
    "connect": "voice join",
    "speak": "voice speak, voice play",
}


def _permission_checks(server: str) -> list[Check]:
    """Check the bot's real permission bitfield in one guild.

    This is the only check that touches the network, which is why it runs
    only when --server is passed: `discli doctor` stays an offline diagnostic
    by default.
    """
    import asyncio

    from discli.client import run_rest_action
    from discli.utils import resolve_guild

    token = os.environ.get("DISCORD_BOT_TOKEN") or load_config().get("token")
    if not token:
        return [
            Check(
                "guild permissions",
                False,
                "no token configured",
                hint="run `discli config set token <TOKEN>` or set DISCORD_BOT_TOKEN",
            )
        ]

    async def action(client):
        guild = await resolve_guild(client, server)
        me = await guild.fetch_member(client.user.id)
        return guild.name, guild.id, me.guild_permissions

    try:
        guild_name, guild_id, perms = asyncio.run(run_rest_action(token, action))
    except Exception as exc:
        return [
            Check(
                "guild permissions",
                False,
                f"lookup failed: {exc}",
                hint=f"check the token, and that the bot is in a server matching '{server}'",
            )
        ]

    checks = [Check("guild", True, f"{guild_name} (ID: {guild_id})")]

    if perms.administrator:
        checks.append(
            Check("administrator", True, "granted — every permission is implied")
        )
        return checks

    regressions = [
        (new_bit, legacy, since, affected)
        for new_bit, legacy, since, affected in PERMISSION_SPLITS
        if getattr(perms, legacy, False) and not getattr(perms, new_bit, False)
    ]
    if regressions:
        detail = "; ".join(
            f"{new} (covered by {legacy} until {since})"
            for new, legacy, since, _ in regressions
        )
        affected = "; ".join(a for *_, a in regressions)
        checks.append(
            Check(
                "permission splits",
                False,
                detail,
                hint=(
                    "This bot holds the old permission but not the split-out one, so it "
                    f"can no longer: {affected}. Re-invite it with an updated permission "
                    "bitfield, or grant these in Server Settings > Roles."
                ),
            )
        )
    else:
        checks.append(Check("permission splits", True, "no regressions"))

    missing = [p for p in DISCLI_PERMISSIONS if not getattr(perms, p, False)]
    granted_count = len(DISCLI_PERMISSIONS) - len(missing)
    detail = f"{granted_count}/{len(DISCLI_PERMISSIONS)} granted"
    if missing:
        detail += " — not granted: " + ", ".join(missing)
    # Always ok: an absent permission is only a problem if you wanted the
    # command that needs it, which doctor cannot know.
    checks.append(Check("discli permissions", True, detail))
    return checks


def _gather(server: str | None = None) -> list[Section]:
    sections: list[Section] = [
        Section(
            "CORE",
            [_check_python(), _check_token(), _check_discord_py()],
        ),
        _voice_section(),
    ]
    # STT/TTS/ffmpeg only matter once voice is on the table. A pure-text dev
    # gets a two-section report (CORE + VOICE-not-configured).
    if _voice_extras_installed():
        sections.extend([_stt_section(), _tts_section()])
        sections.append(Section("TOOLS", [_check_ffmpeg()]))

    if server:
        sections.append(Section("PERMISSIONS", _permission_checks(server)))
    else:
        sections.append(
            Section(
                "PERMISSIONS",
                [
                    Check(
                        "guild permissions",
                        False,
                        "not checked",
                        hint="pass --server <name-or-id> to verify the bot's permission bitfield",
                        skipped=True,
                    )
                ],
            )
        )
    return sections


def _format_text(sections: list[Section]) -> tuple[str, int, int]:
    """Return (rendered text, failure count, skipped/optional count)."""
    lines: list[str] = []
    failures = 0
    skipped = 0
    for section in sections:
        lines.append(section.name)
        for check in section.checks:
            if check.skipped:
                marker = "[--]"
                skipped += 1
            elif check.ok:
                marker = "[ok]"
            else:
                marker = "[FAIL]"
                failures += 1
            detail = f" — {check.detail}" if check.detail else ""
            lines.append(f"  {marker} {check.name}{detail}")
            if check.hint and not check.ok:
                lines.append(f"        hint: {check.hint}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", failures, skipped


@click.command("doctor")
@click.option(
    "--server",
    default=None,
    help="Also check the bot's permission bitfield in this server (name or ID). Requires network.",
)
@click.pass_context
def doctor_cmd(ctx, server):
    """Diagnose the local install: token, voice deps, STT/TTS keys, ffmpeg.

    Optional dependencies (voice extras, STT/TTS keys, ffmpeg) are reported
    as `[--]` rather than failures when not installed — so devs who only use
    text features see a clean report. Only genuine breakage (missing core
    deps, wrong voice_recv version, libopus failing to load) counts as a
    failure.

    Every check is local unless `--server` is given, which adds a PERMISSIONS
    section that logs in and reads the bot's real permissions in that guild.
    That section flags permissions Discord split out of broader ones during
    2026 — a bot invited before the split keeps the old bit and silently
    loses the new capability, which nothing else here can detect.

    Exits 0 when no failures; 1 otherwise. Use `--json` for scripting.
    """
    sections = _gather(server)
    use_json = ctx.obj.get("use_json", False) if ctx.obj else False

    if use_json:
        payload = {
            "sections": [
                {
                    "name": section.name,
                    "checks": [
                        {
                            "name": c.name,
                            "ok": c.ok,
                            "detail": c.detail,
                            "hint": c.hint,
                            "skipped": c.skipped,
                        }
                        for c in section.checks
                    ],
                }
                for section in sections
            ],
        }
        failures = sum(
            1 for s in sections for c in s.checks if not c.ok and not c.skipped
        )
        payload["failures"] = failures
        click.echo(json_mod.dumps(payload, indent=2))
        ctx.exit(0 if failures == 0 else 1)

    text, failures, skipped = _format_text(sections)
    click.echo(text, nl=False)
    if failures == 0:
        click.echo(
            f"OK — no problems found ({skipped} optional check(s) skipped)."
        )
        ctx.exit(0)
    else:
        click.echo(f"{failures} problem(s) found. See hints above.", err=True)
        ctx.exit(1)
