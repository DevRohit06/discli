import click

from discli.client import run_discord
from discli.security import audit_log, confirm_destructive, rate_limiter
from discli.utils import output, resolve_guild


def resolve_member(guild, identifier: str):
    """Resolve a member by ID or name."""
    try:
        member_id = int(identifier)
        member = guild.get_member(member_id)
        if member:
            return member
    except ValueError:
        pass
    for member in guild.members:
        if member.name.lower() == identifier.lower() or str(member).lower() == identifier.lower():
            return member
    raise click.ClickException(f"Member not found: {identifier}")


@click.group("member")
def member_group():
    """List, inspect, kick, ban, and unban members."""


@member_group.command("list")
@click.argument("server")
@click.option("--limit", default=50, help="Max members to list.")
@click.pass_context
def member_list(ctx, server, limit):
    """List members of a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            members = []
            for m in guild.members[:limit]:
                members.append({
                    "id": str(m.id),
                    "name": str(m),
                    "nick": m.nick,
                    "bot": m.bot,
                })
            plain_lines = []
            for m in members:
                parts = [m["name"]]
                if m["bot"]:
                    parts.append("(bot)")
                if m["nick"]:
                    parts.append(f"aka {m['nick']}")
                plain_lines.append(" ".join(parts))
            output(ctx, members, plain_text="\n".join(plain_lines) if plain_lines else "No members found.")
        return _action(client)

    run_discord(ctx, action)


@member_group.command("info")
@click.argument("server")
@click.argument("member")
@click.pass_context
def member_info(ctx, server, member):
    """Show member details."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            data = {
                "id": str(m.id),
                "name": str(m),
                "nick": m.nick,
                "bot": m.bot,
                "roles": [r.name for r in m.roles if r.name != "@everyone"],
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items() if v is not None]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)


@member_group.command("kick")
@click.argument("server")
@click.argument("member")
@click.option("--reason", default=None, help="Reason for kick.")
@click.option("--triggered-by", default=None, help="User ID who triggered this action (for permission check).")
@click.pass_context
def member_kick(ctx, server, member, reason, triggered_by):
    """Kick a member from the server."""
    confirm_destructive("member kick", f"{member} from {server}")

    def action(client):
        async def _action(client):
            rate_limiter.wait()
            guild = resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                check_user_permission(guild, int(triggered_by), "kick")
            m = resolve_member(guild, member)
            name = str(m)
            await m.kick(reason=reason)
            audit_log("member kick", {"server": server, "member": name, "reason": reason}, user=triggered_by or "")
            output(ctx, {"member": name, "kicked": True}, plain_text=f"Kicked {name}")
        return _action(client)

    run_discord(ctx, action)


@member_group.command("ban")
@click.argument("server")
@click.argument("member")
@click.option("--reason", default=None, help="Reason for ban.")
@click.option("--triggered-by", default=None, help="User ID who triggered this action (for permission check).")
@click.pass_context
def member_ban(ctx, server, member, reason, triggered_by):
    """Ban a member from the server."""
    confirm_destructive("member ban", f"{member} from {server}")

    def action(client):
        async def _action(client):
            rate_limiter.wait()
            guild = resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                check_user_permission(guild, int(triggered_by), "ban")
            m = resolve_member(guild, member)
            name = str(m)
            await m.ban(reason=reason)
            audit_log("member ban", {"server": server, "member": name, "reason": reason}, user=triggered_by or "")
            output(ctx, {"member": name, "banned": True}, plain_text=f"Banned {name}")
        return _action(client)

    run_discord(ctx, action)


@member_group.command("unban")
@click.argument("server")
@click.argument("member")
@click.option("--triggered-by", default=None, help="User ID who triggered this action (for permission check).")
@click.pass_context
def member_unban(ctx, server, member, triggered_by):
    """Unban a member from the server."""
    confirm_destructive("member unban", f"{member} from {server}")

    def action(client):
        async def _action(client):
            rate_limiter.wait()
            guild = resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                check_user_permission(guild, int(triggered_by), "ban")
            bans = [b async for b in guild.bans()]
            target = None
            for ban_entry in bans:
                u = ban_entry.user
                if str(u.id) == member or str(u).lower() == member.lower():
                    target = u
                    break
            if not target:
                raise click.ClickException(f"Banned user not found: {member}")
            await guild.unban(target)
            audit_log("member unban", {"server": server, "member": str(target)}, user=triggered_by or "")
            output(ctx, {"member": str(target), "unbanned": True}, plain_text=f"Unbanned {target}")
        return _action(client)

    run_discord(ctx, action)
