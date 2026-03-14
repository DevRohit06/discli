import asyncio

import click

from discli.client import run_discord
from discli.utils import resolve_channel


@click.command("typing")
@click.argument("channel")
@click.option("--duration", default=5, help="Seconds to show typing indicator (default: 5).")
@click.pass_context
def typing_cmd(ctx, channel, duration):
    """Show typing indicator in a channel."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            async with ch.typing():
                await asyncio.sleep(duration)
            click.echo(f"Typed in #{ch.name} for {duration}s")
        return _action(client)

    run_discord(ctx, action)
