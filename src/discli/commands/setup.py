"""`discli setup` — the interactive first-run wizard.

Automates what README's Setup section asks people to do by hand: store a
bot token, invite the bot with the right permission bitfield, choose a
permission profile, and point voice users at the environment variables
their providers read.

This is the only command in discli that *requires* a human. Everything
else is designed to be driven by an agent over a pipe, so the wizard
refuses immediately when there is no terminal rather than blocking on a
prompt nobody will answer.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys

import click

GUILD_PREVIEW = 10

NON_INTERACTIVE_HELP = """setup is interactive and needs a terminal.
Non-interactive equivalents:
  discli config set token <TOKEN>
  discli permission set <profile>
  discli doctor --json"""


def _is_interactive() -> bool:
    """True when a human can both see a prompt and answer it.

    Both streams matter. click writes prompts to stdout, so under
    ``discli setup > setup.log`` stdin is still a tty and a stdin-only check
    passes -- while every question disappears into the file and the terminal
    looks hung. That is the failure this guard exists to prevent, so a
    redirected stdout counts as non-interactive too.

    Wrapped in a function so tests can drive the wizard: click's CliRunner
    feeds stdin from a StringIO, which is never a tty, so an inline
    ``isatty()`` would make every prompt path untestable.
    """
    for stream in (sys.stdin, sys.stdout):
        try:
            if stream is None or not stream.isatty():
                return False
        except (AttributeError, ValueError):
            # Detached or closed stream (some CI harnesses) -- not a human.
            return False
    return True


# Capability bundles offered at the invite step. Every name here must be a
# real discord.Permissions flag *and* appear in doctor's DISCLI_PERMISSIONS,
# so the invite the wizard generates and the permissions doctor checks for
# stay the same set. test_every_bundled_permission_is_one_discli_actually_uses pins it.
BUNDLES: dict[str, tuple[str, list[str]]] = {
    "messaging": (
        "Read and send messages, embeds, files, reactions, polls, threads",
        [
            "view_channel", "read_message_history", "send_messages",
            "embed_links", "attach_files", "add_reactions", "send_polls",
            "create_public_threads",
        ],
    ),
    "moderation": (
        "Delete and pin messages, kick, ban, timeout, rename members",
        [
            # bypass_slowmode and pin_messages were split out of
            # manage_messages during 2026. Granting the legacy bit without
            # them is the exact regression doctor's PERMISSION_SPLITS check
            # reports, so the wizard would print an invite that fails its
            # own step 5.
            "manage_messages", "pin_messages", "bypass_slowmode",
            "kick_members", "ban_members",
            "moderate_members", "manage_nicknames",
        ],
    ),
    "voice": (
        "Join voice channels, speak, move members between them",
        ["connect", "speak", "move_members"],
    ),
    "admin": (
        "Create/edit channels and roles, webhooks, invites, emoji, events, audit log",
        [
            "manage_channels", "manage_roles", "manage_guild", "view_audit_log",
            "manage_webhooks", "create_instant_invite", "create_expressions",
            "manage_expressions", "create_events", "manage_events",
        ],
    ),
}


def _export_lines(assignments: list[tuple[str, str]], *, windows: bool) -> list[str]:
    """Render environment assignments in the syntax of the user's shell.

    The provider credentials in ``tts.py``/``stt.py`` are read from the
    environment, never from config.json, so the wizard can only tell people
    what to set -- and a line in the wrong dialect is a line that silently
    does nothing.
    """
    if windows:
        return [f'setx {name} "{value}"' for name, value in assignments]
    return [f"export {name}={shlex.quote(value)}" for name, value in assignments]


def _invite_url(client_id: int, permission_names: list[str]) -> str:
    """Build the OAuth2 invite URL for a permission set.

    A bot user's ID and its application ID are the same value, so the login
    from the token step supplies the client_id and the wizard never has to
    ask for it separately.
    """
    import discord

    return discord.utils.oauth_url(
        client_id,
        permissions=discord.Permissions(**{name: True for name in permission_names}),
    )


async def _identify(client) -> dict:
    """Read back who a validated token actually belongs to.

    Pasting the token of a *different* application is the likeliest mistake
    at this step, and it fails silently -- the login succeeds, and every
    later command quietly targets the wrong bot. Showing the name and a few
    of the servers it is already in is what makes that visible.

    Capped deliberately: proving *which* bot this is does not justify
    paginating every guild of a bot that is in hundreds, nor rendering all
    their names into one wrapped line.
    """
    cached = list(getattr(client, "guilds", ()))
    if cached:
        names = [g.name for g in cached]
    else:
        # PREVIEW+1 so one extra proves there are more, without paying for
        # the remaining pages.
        names = [g.name async for g in client.fetch_guilds(limit=GUILD_PREVIEW + 1)]
    return {
        "id": client.user.id,
        "name": str(client.user),
        "guilds": names[:GUILD_PREVIEW],
        "more": max(0, len(names) - GUILD_PREVIEW),
    }


def _validate_token(token: str) -> dict:
    """Log in with a token and report who it belongs to."""
    import asyncio

    from discli.client import run_rest_action

    return asyncio.run(run_rest_action(token, _identify))


def _step_token() -> dict:
    """Store a bot token, but only one that has been proven to work.

    Saving first and verifying later is the tempting order and the wrong
    one: it leaves a broken token in config.json that every later command
    picks up, and the failure surfaces far from the mistake.
    """
    import discord

    from discli.config import load_config, save_config

    click.echo("1. Bot token")
    env_bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    stored = load_config().get("token")
    if env_bot_token:
        # cli.py reads the envvar before falling back to config.json, so a
        # token saved here would be shadowed and the user would never know.
        click.echo(
            "   Note: DISCORD_BOT_TOKEN is set in your environment and takes "
            "precedence over the stored token."
        )

    candidate = env_bot_token or stored or os.environ.get("DISCORD_TOKEN")
    if candidate and not click.confirm(
        "   Use the token already configured?", default=True
    ):
        candidate = None

    for attempts_left in (2, 1, 0):
        if not candidate:
            candidate = click.prompt("   Paste your bot token", hide_input=True).strip()
        try:
            info = _validate_token(candidate)
        except discord.LoginFailure:
            click.echo("   Discord rejected that token.", err=True)
        except Exception as exc:  # network, DNS, a proxy in the way
            click.echo(f"   Could not verify that token: {exc}", err=True)
        else:
            where = ", ".join(info["guilds"]) or "no servers yet - see step 2"
            if info["more"]:
                # Exact when the client had a cache, "at least one" when it
                # came from a bounded fetch -- so no number is claimed.
                where += ", and more"
            click.echo(f"   OK - {info['name']} (ID: {info['id']}), in: {where}")
            if candidate != stored:
                save_config({"token": candidate})
                click.echo("   Saved to ~/.discli/config.json")
                if env_bot_token and candidate != env_bot_token:
                    # The note before the prompt is far away by now, and this
                    # is the case where it decides the outcome: every command
                    # will keep resolving the environment token, not this one.
                    click.echo(
                        "   Warning: DISCORD_BOT_TOKEN is set and still takes precedence "
                        "over what was just saved.",
                        err=True,
                    )
                    click.echo("   Unset it to use the saved token.", err=True)
            return info
        candidate = None
        if not attempts_left:
            break

    raise click.ClickException(
        "No working bot token. Create one at "
        "https://discord.com/developers/applications and run `discli setup` again."
    )


def _step_invite(info: dict) -> None:
    """Offer an invite URL carrying exactly the permissions they asked for."""
    click.echo()
    click.echo("2. Invite the bot to a server")
    chosen: list[str] = []
    for bundle, (description, names) in BUNDLES.items():
        if click.confirm(f"   Grant {bundle}? ({description})", default=bundle == "messaging"):
            chosen.extend(names)

    if not chosen:
        click.echo("   Nothing selected - skipping the invite URL.")
        return

    ordered = list(dict.fromkeys(chosen))
    click.echo("   Open this URL to invite the bot:")
    click.echo(f"   {_invite_url(info['id'], ordered)}")
    # Intents are an application setting, not an OAuth scope -- no invite URL
    # can turn them on, and a missing one fails the whole Gateway connection.
    click.echo("   Privileged intents cannot be granted by a URL. If you need them,")
    click.echo("   enable them under Developer Portal > Bot > Privileged Gateway Intents:")
    click.echo("     Message Content - message text in `discli listen` and `discli serve`")
    click.echo("     Server Members  - `discli member list` and name lookups")


def _step_profile() -> None:
    """Choose how much of discli this machine is allowed to drive."""
    from discli.security import get_active_profile_name, get_profiles, set_active_profile

    click.echo()
    click.echo("3. Permission profile")
    current = get_active_profile_name()
    # Built-ins plus any custom profile, so an active custom one is still a
    # valid choice -- offering it as a default click.Choice would reject
    # rules out keeping what is already configured.
    profiles = get_profiles()
    for name, profile in profiles.items():
        marker = "*" if name == current else " "
        click.echo(f"   {marker} {name}: {profile.get('description', 'custom profile')}")

    chosen = click.prompt(
        "   Profile",
        type=click.Choice(list(profiles)),
        default=current,
        show_choices=False,
    )
    set_active_profile(chosen)
    click.echo(f"   Active profile: {chosen}")
    if chosen != "full":
        # setup writes the token and sets the profile, so it is full-only --
        # which means this choice is also the one that locks them out of
        # re-running the wizard. Say so here, where it is actionable.
        click.echo("   Note: `discli setup` requires the full profile, so re-run it with:")
        click.echo("     discli --profile full setup")


# Provider -> the credential its implementation reads. Kept in step with
# get_tts_provider()/get_stt_provider(), which are the functions that will
# actually reject an unknown name at runtime.
TTS_PROVIDERS = ["elevenlabs", "openai", "deepgram", "none"]
STT_PROVIDERS = ["deepgram", "openai", "none"]
PROVIDER_KEYS = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepgram": "DEEPGRAM_API_KEY",
}


def _windows_shell() -> bool:
    """True when the user's shell wants `setx` rather than `export`.

    os.name is "nt" inside Git Bash and MSYS too -- the shell this repo's
    own tooling runs in -- where setx is either absent or sets a variable
    bash will never read. MSYSTEM/SHELL is the giveaway.
    """
    if os.environ.get("MSYSTEM") or os.environ.get("SHELL"):
        return False
    return os.name == "nt"


def _configured(value: str | None, valid: list[str]) -> str:
    """An already-exported provider, if it is one we can offer."""
    return value if value in valid else "none"


def _step_voice() -> None:
    """Point voice users at the environment variables their providers read.

    Deliberately writes nothing: tts.py and stt.py read credentials from the
    environment only, so anything persisted here would be a file discli
    never consults.
    """
    from discli.commands.doctor import _voice_extras_installed

    click.echo()
    click.echo("4. Voice (optional)")

    installed = _voice_extras_installed()
    # The skip has to exist in both branches. Someone who installed the
    # extras for `voice play` alone still never wants TTS or STT, and this
    # step is advertised as optional.
    question = (
        "   Configure speech providers now?" if installed
        else "   Voice extras are not installed. Set voice up now?"
    )
    if not click.confirm(question, default=False):
        click.echo("   Skipped.")
        return

    if not installed:
        click.echo("   Install the extras first:")
        click.echo("     pip install 'discord-cli-agent[voice,deepgram]'")

    if shutil.which("ffmpeg") is None:
        click.echo("   ffmpeg is not on PATH - `voice play` and TTS playback need it.")

    # Default to what is already exported, so re-running the wizard keeps a
    # working setup instead of offering to switch it off.
    tts = click.prompt(
        "   TTS provider (speech out)",
        type=click.Choice(TTS_PROVIDERS),
        default=_configured(os.environ.get("DISCLI_TTS"), TTS_PROVIDERS),
        show_choices=True,
    )
    stt = click.prompt(
        "   STT provider (speech in)",
        type=click.Choice(STT_PROVIDERS),
        default=_configured(os.environ.get("DISCLI_STT"), STT_PROVIDERS),
        show_choices=True,
    )

    assignments: list[tuple[str, str]] = []
    if tts != "none":
        assignments.append(("DISCLI_TTS", tts))
    if stt != "none":
        assignments.append(("DISCLI_STT", stt))
    if not assignments:
        click.echo("   No providers selected.")
        return

    needed = {PROVIDER_KEYS[p] for p in (tts, stt) if p in PROVIDER_KEYS}
    already = sorted(k for k in needed if os.environ.get(k))
    assignments += [(k, "<your-key>") for k in sorted(needed - set(already))]

    windows = _windows_shell()
    if windows:
        # setx writes the persistent environment and explicitly does NOT
        # affect the current console, so "add to your profile" is wrong.
        click.echo("   Run these once, then open a new terminal:")
    else:
        click.echo("   Add these to your shell profile:")
    for line in _export_lines(assignments, windows=windows):
        click.echo(f"     {line}")
    if already:
        click.echo(f"   Already set: {', '.join(already)}")


def _step_verify() -> int:
    """Close with doctor's own report rather than a second opinion."""
    from discli.commands.doctor import _format_text, _gather

    click.echo()
    click.echo("5. Verify")
    text, failures, _skipped = _format_text(_gather(None))
    click.echo(text, nl=False)
    if failures:
        click.echo(f"   {failures} problem(s) above. Re-run `discli doctor` after fixing.")
    else:
        click.echo("   Ready. Try: discli server list")
    return failures


@click.command("setup")
@click.pass_context
def setup_cmd(ctx):
    """Interactively configure discli: token, invite, profile, voice.

    Walks through storing a bot token that has been checked against Discord,
    generating an invite URL carrying the permissions you pick, choosing a
    permission profile, and naming the environment variables voice providers
    read. Ends with the same report `discli doctor` prints.

    Every step shows what is already configured and offers to keep it, so
    re-running this is safe.

    Requires a terminal. With `--json`, or when stdin is piped, it exits 1
    rather than blocking on a prompt nobody will answer -- use `config set
    token` and `permission set` from scripts instead.
    """
    # Deny before prompting, matching confirm_destructive(). This command
    # writes the token and sets the active profile, so a restricted profile
    # that could run it could promote itself to full.
    from discli.client import enforce_profile

    enforce_profile(ctx)

    if ctx.obj.get("use_json") or not _is_interactive():
        click.echo(NON_INTERACTIVE_HELP, err=True)
        ctx.exit(1)

    click.echo("discli setup - press Ctrl-C at any point to stop.")
    click.echo()
    info = _step_token()
    _step_invite(info)
    _step_profile()
    _step_voice()
    # Exit like doctor does. Reporting failures and still exiting 0 makes
    # `discli setup && echo ready` print ready for a broken install.
    if _step_verify():
        ctx.exit(1)
