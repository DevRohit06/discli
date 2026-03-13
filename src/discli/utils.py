import json
from typing import Any

import click


def format_output(data: Any, use_json: bool = False) -> str:
    if use_json:
        return json.dumps(data, indent=2, default=str)
    return str(data)


def output(ctx: click.Context, data: Any, plain_text: str | None = None) -> None:
    """Print output respecting --json flag."""
    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(format_output(data, use_json=True))
    else:
        click.echo(plain_text if plain_text is not None else format_output(data))


def resolve_channel(client, identifier: str):
    """Resolve a channel by ID or #name."""
    if identifier.startswith("#"):
        name = identifier[1:]
        for guild in client.guilds:
            for ch in guild.text_channels:
                if ch.name == name:
                    return ch
        raise click.ClickException(f"Channel not found: #{name}")
    else:
        try:
            channel = client.get_channel(int(identifier))
            if channel is None:
                raise click.ClickException(f"Channel not found: {identifier}")
            return channel
        except ValueError:
            raise click.ClickException(f"Invalid channel identifier: {identifier}")


def resolve_guild(client, identifier: str):
    """Resolve a guild/server by ID or name."""
    try:
        guild_id = int(identifier)
        guild = client.get_guild(guild_id)
        if guild:
            return guild
    except ValueError:
        pass
    for guild in client.guilds:
        if guild.name.lower() == identifier.lower():
            return guild
    raise click.ClickException(f"Server not found: {identifier}")
