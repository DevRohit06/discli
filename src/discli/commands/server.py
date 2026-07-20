import click

from discli.client import run_rest
from discli.utils import fetch_guilds, output, resolve_guild


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
            for g in await fetch_guilds(client):
                member_count = g.member_count
                if member_count is None:
                    member_count = g.approximate_member_count
                servers.append({
                    "id": str(g.id),
                    "name": g.name,
                    "member_count": member_count,
                })
            plain_lines = [f"{s['name']} (ID: {s['id']}, members: {s['member_count']})" for s in servers]
            output(ctx, servers, plain_text="\n".join(plain_lines) if plain_lines else "Bot is not in any servers.")
        return _action(client)

    run_rest(ctx, action)


@server_group.command("info")
@click.argument("server")
@click.pass_context
def server_info(ctx, server):
    """Show server details."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            channels = await guild.fetch_channels()
            roles = await guild.fetch_roles()
            member_count = guild.member_count
            if member_count is None:
                member_count = guild.approximate_member_count
            owner = str(guild.owner_id)
            if guild.owner_id:
                try:
                    owner = str(await guild.fetch_member(guild.owner_id))
                except Exception:
                    pass
            data = {
                "id": str(guild.id),
                "name": guild.name,
                "owner": owner,
                "member_count": member_count,
                "channel_count": len(channels),
                "role_count": len(roles),
                "created_at": guild.created_at.isoformat(),
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items()]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_rest(ctx, action)
