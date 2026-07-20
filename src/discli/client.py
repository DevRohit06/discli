import asyncio
from collections.abc import Iterable
from typing import Any, Callable, Coroutine

import click
import discord


Action = Callable[[discord.Client], Coroutine[Any, Any, Any]]

EVENT_FEATURES = {
    "messages": "messages",
    "edits": "messages",
    "deletes": "messages",
    "reactions": "reactions",
    "members": "members",
    "voice": "voice",
}


def resolve_token(token: str | None, config: dict) -> str:
    if token:
        return token
    config_token = config.get("token")
    if config_token:
        return config_token
    raise click.ClickException(
        "No token provided. Use --token, set DISCORD_BOT_TOKEN, or run: discli config set token YOUR_TOKEN"
    )


def build_gateway_intents(features: Iterable[str] = ()) -> discord.Intents:
    """Build the smallest Gateway intent set needed for selected features."""
    selected = set(features)
    intents = discord.Intents.none()
    intents.guilds = True

    if "messages" in selected:
        intents.guild_messages = True
        intents.dm_messages = True
        intents.message_content = True
    if "reactions" in selected:
        # discord.py's cached reaction events need message create events to
        # populate the message cache, but they do not need message content.
        intents.guild_messages = True
        intents.dm_messages = True
        intents.guild_reactions = True
        intents.dm_reactions = True
    if "members" in selected:
        intents.members = True
    if "voice" in selected:
        intents.voice_states = True

    return intents


def gateway_features_for_events(events: set[str] | None) -> set[str]:
    """Translate listen/serve event filters into Gateway feature names."""
    selected_events = events if events is not None else set(EVENT_FEATURES)
    return {EVENT_FEATURES[event] for event in selected_events if event in EVENT_FEATURES}


async def run_rest_action(token: str, action: Action) -> Any:
    """Authenticate for HTTP operations without opening a Gateway session."""
    client = discord.Client(intents=discord.Intents.none())
    try:
        await client.login(token)
        return await action(client)
    finally:
        await client.close()


async def run_gateway_action(
    token: str,
    action: Action,
    intents: discord.Intents,
) -> Any:
    """Open one Gateway session, run an action after Ready, then disconnect."""
    client = discord.Client(intents=intents)
    result = None
    error = None

    @client.event
    async def on_ready():
        nonlocal result, error
        try:
            result = await action(client)
        except Exception as exc:
            error = exc
        finally:
            await client.close()

    try:
        await client.start(token)
    finally:
        if not client.is_closed():
            await client.close()

    if error:
        raise error
    return result


def _check_permission(ctx: click.Context) -> None:
    from discli.security import is_command_allowed

    command_path = ctx.command_path.removeprefix("main ")
    if command_path.startswith("discli "):
        command_path = command_path[7:]
    profile = ctx.obj.get("profile")
    if not is_command_allowed(command_path, profile_override=profile):
        raise click.ClickException(
            f"Command '{command_path}' is denied by the '{profile or 'active'}' permission profile. "
            "Run 'discli permission show' to see active profile."
        )


def _run(ctx: click.Context, operation: Coroutine[Any, Any, Any]) -> Any:
    try:
        return asyncio.run(operation)
    except discord.LoginFailure:
        raise click.ClickException("Invalid bot token.")
    except discord.PrivilegedIntentsRequired:
        raise click.ClickException(
            "Discord rejected a required privileged Gateway intent. Enable only the intent "
            "needed by this Gateway command in Developer Portal > Bot > Privileged Gateway Intents."
        )
    except discord.Forbidden as exc:
        raise click.ClickException(f"Discord API permission denied: {exc}")
    except discord.NotFound as exc:
        raise click.ClickException(f"Discord resource not found: {exc}")
    except discord.HTTPException as exc:
        raise click.ClickException(f"Discord API error: {exc}")


def run_rest(ctx: click.Context, action: Action) -> Any:
    """Run a one-shot Discord HTTP action without connecting to Gateway."""
    _check_permission(ctx)
    token = resolve_token(ctx.obj.get("token"), {})
    return _run(ctx, run_rest_action(token, action))


def run_gateway(
    ctx: click.Context,
    action: Action,
    *,
    features: Iterable[str] = (),
) -> Any:
    """Run a one-shot action that genuinely requires Gateway state."""
    _check_permission(ctx)
    token = resolve_token(ctx.obj.get("token"), {})
    intents = build_gateway_intents(features)
    return _run(ctx, run_gateway_action(token, action, intents))


# Backward compatibility for external imports. One-shot commands are REST by default.
run_discord = run_rest
