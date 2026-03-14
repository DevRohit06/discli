import asyncio
from typing import Any, Callable, Coroutine

import click
import discord


def resolve_token(token: str | None, config: dict) -> str:
    if token:
        return token
    config_token = config.get("token")
    if config_token:
        return config_token
    raise click.ClickException(
        "No token provided. Use --token, set DISCORD_BOT_TOKEN, or run: discli config set token YOUR_TOKEN"
    )


async def run_action(token: str, action: Callable[[discord.Client], Coroutine[Any, Any, Any]]) -> Any:
    """Connect a bot client, run an action on_ready, return the result, disconnect."""
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    result = None
    error = None

    @client.event
    async def on_ready():
        nonlocal result, error
        try:
            result = await action(client)
        except Exception as e:
            error = e
        finally:
            await client.close()

    await client.start(token)

    if error:
        raise error
    return result


def run_discord(ctx, action: Callable[[discord.Client], Coroutine[Any, Any, Any]]) -> Any:
    """Synchronous entry point: resolve token, check permissions, run action, return result."""
    # Check permission profile with full command path (e.g. "message send")
    from discli.security import is_command_allowed
    command_path = ctx.command_path.removeprefix("main ")  # "discli message send" → "message send"
    if command_path.startswith("discli "):
        command_path = command_path[7:]
    profile = ctx.obj.get("profile")
    if not is_command_allowed(command_path, profile_override=profile):
        raise click.ClickException(
            f"Command '{command_path}' is denied by the '{profile or 'active'}' permission profile. "
            "Run 'discli permission show' to see active profile."
        )

    token = resolve_token(ctx.obj.get("token"), {})
    try:
        return asyncio.run(run_action(token, action))
    except discord.LoginFailure:
        raise click.ClickException("Invalid bot token.")
    except discord.HTTPException as e:
        raise click.ClickException(f"Discord API error: {e}")
