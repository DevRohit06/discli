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
    """Synchronous entry point: resolve token, run action, return result."""
    token = resolve_token(ctx.obj.get("token"), {})
    try:
        return asyncio.run(run_action(token, action))
    except discord.LoginFailure:
        raise click.ClickException("Invalid bot token.")
    except discord.HTTPException as e:
        raise click.ClickException(f"Discord API error: {e}")
