import click

from discli.client import run_discord
from discli.utils import output, resolve_guild


@click.group("server")
def server_group():
    """List and inspect servers."""


@server_group.command("list")
@click.pass_context
def server_list(ctx):
    """List servers the bot is in."""

    def action(client):
        async def _action(client):
            servers = []
            for g in client.guilds:
                servers.append({
                    "id": str(g.id),
                    "name": g.name,
                    "member_count": g.member_count,
                })
            plain_lines = [f"{s['name']} (ID: {s['id']}, members: {s['member_count']})" for s in servers]
            output(ctx, servers, plain_text="\n".join(plain_lines) if plain_lines else "Bot is not in any servers.")
        return _action(client)

    run_discord(ctx, action)


@server_group.command("info")
@click.argument("server")
@click.pass_context
def server_info(ctx, server):
    """Show server details."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            data = {
                "id": str(guild.id),
                "name": guild.name,
                "owner": str(guild.owner),
                "member_count": guild.member_count,
                "channel_count": len(guild.channels),
                "role_count": len(guild.roles),
                "created_at": guild.created_at.isoformat(),
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items()]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)
