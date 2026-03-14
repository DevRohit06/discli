import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel, resolve_guild


@click.group("channel")
def channel_group():
    """List, create, delete, and inspect channels."""


@channel_group.command("list")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def channel_list(ctx, server):
    """List channels in a server."""

    def action(client):
        async def _action(client):
            if server:
                guilds = [resolve_guild(client, server)]
            else:
                guilds = client.guilds
            channels = []
            for g in guilds:
                for ch in g.channels:
                    if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                        channels.append({
                            "id": str(ch.id),
                            "name": ch.name,
                            "type": str(ch.type),
                            "server": g.name,
                        })
            plain_lines = [f"#{c['name']} ({c['type']}) — {c['server']} (ID: {c['id']})" for c in channels]
            output(ctx, channels, plain_text="\n".join(plain_lines) if plain_lines else "No channels found.")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("create")
@click.argument("server")
@click.argument("name")
@click.option("--type", "channel_type", type=click.Choice(["text", "voice", "category"]), default="text")
@click.pass_context
def channel_create(ctx, server, name, channel_type):
    """Create a channel in a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            if channel_type == "text":
                ch = await guild.create_text_channel(name)
            elif channel_type == "voice":
                ch = await guild.create_voice_channel(name)
            else:
                ch = await guild.create_category(name)
            data = {"id": str(ch.id), "name": ch.name, "type": str(ch.type)}
            output(ctx, data, plain_text=f"Created #{ch.name} (ID: {ch.id})")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("delete")
@click.argument("channel")
@click.pass_context
def channel_delete(ctx, channel):
    """Delete a channel."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("channel delete", channel)

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            name = ch.name
            await ch.delete()
            audit_log("channel delete", {"channel": name})
            output(ctx, {"id": str(ch.id), "deleted": True}, plain_text=f"Deleted #{name}")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("info")
@click.argument("channel")
@click.pass_context
def channel_info(ctx, channel):
    """Show channel details."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            data = {
                "id": str(ch.id),
                "name": ch.name,
                "type": str(ch.type),
                "server": ch.guild.name,
                "topic": getattr(ch, "topic", None),
                "created_at": ch.created_at.isoformat(),
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items() if v is not None]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)
