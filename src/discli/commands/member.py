import click

from discli.client import run_rest
from discli.security import audit_log, confirm_destructive, rate_limiter
from discli.utils import output, resolve_guild, resolve_member


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
            guild = await resolve_guild(client, server)
            members = []
            fetched_members = [m async for m in guild.fetch_members(limit=limit)]
            for m in fetched_members:
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

    run_rest(ctx, action)


@member_group.command("info")
@click.argument("server")
@click.argument("member")
@click.pass_context
def member_info(ctx, server, member):
    """Show member details."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            m = await resolve_member(guild, member)
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

    run_rest(ctx, action)


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
            guild = await resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                await check_user_permission(guild, int(triggered_by), "kick")
            m = await resolve_member(guild, member)
            name = str(m)
            await m.kick(reason=reason)
            audit_log("member kick", {"server": server, "member": name, "reason": reason}, user=triggered_by or "")
            output(ctx, {"member": name, "kicked": True}, plain_text=f"Kicked {name}")
        return _action(client)

    run_rest(ctx, action)


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
            guild = await resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                await check_user_permission(guild, int(triggered_by), "ban")
            m = await resolve_member(guild, member)
            name = str(m)
            await m.ban(reason=reason)
            audit_log("member ban", {"server": server, "member": name, "reason": reason}, user=triggered_by or "")
            output(ctx, {"member": name, "banned": True}, plain_text=f"Banned {name}")
        return _action(client)

    run_rest(ctx, action)


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
            guild = await resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                await check_user_permission(guild, int(triggered_by), "ban")
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

    run_rest(ctx, action)


@member_group.command("timeout")
@click.argument("server")
@click.argument("member")
@click.argument("duration", type=int)
@click.option("--reason", default=None, help="Reason for timeout.")
@click.option("--triggered-by", default=None, help="User ID who triggered this action.")
@click.pass_context
def member_timeout(ctx, server, member, duration, reason, triggered_by):
    """Timeout a member for N seconds (max 2419200 = 28 days). Use 0 to remove timeout."""
    confirm_destructive("member timeout", f"{member} in {server} for {duration}s")

    def action(client):
        async def _action(client):
            from datetime import timedelta
            rate_limiter.wait()
            guild = await resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                await check_user_permission(guild, int(triggered_by), "moderate_members")
            m = await resolve_member(guild, member)
            if duration < 0:
                raise click.ClickException("Duration must be >= 0")
            if duration > 2419200:
                raise click.ClickException("Duration cannot exceed 2419200 seconds (28 days)")
            name = str(m)
            if duration == 0:
                await m.timeout(None, reason=reason)
                audit_log("member timeout_remove", {"server": server, "member": name}, user=triggered_by or "")
                output(ctx, {"member": name, "timeout_removed": True}, plain_text=f"Removed timeout from {name}")
            else:
                await m.timeout(timedelta(seconds=duration), reason=reason)
                audit_log("member timeout", {"server": server, "member": name, "duration": duration, "reason": reason}, user=triggered_by or "")
                output(ctx, {"member": name, "timeout_seconds": duration}, plain_text=f"Timed out {name} for {duration}s")
        return _action(client)

    run_rest(ctx, action)


@member_group.command("nick")
@click.argument("server")
@click.argument("member")
@click.argument("nickname", required=False)
@click.option("--clear", "clear_nick", is_flag=True, default=False, help="Remove the nickname instead of setting one.")
@click.option("--reason", default=None, help="Audit log reason.")
@click.option("--triggered-by", default=None, help="User ID who triggered this action.")
@click.pass_context
def member_nick(ctx, server, member, nickname, clear_nick, reason, triggered_by):
    """Set or clear a member's server nickname."""
    if clear_nick and nickname is not None:
        raise click.ClickException("Pass either a nickname or --clear, not both.")
    if not clear_nick and nickname is None:
        raise click.ClickException("Provide a nickname, or use --clear to remove it.")
    if nickname is not None and len(nickname) > 32:
        raise click.ClickException("Nicknames cannot exceed 32 characters.")

    def action(client):
        async def _action(client):
            rate_limiter.wait()
            guild = await resolve_guild(client, server)
            if triggered_by:
                from discli.security import check_user_permission
                await check_user_permission(guild, int(triggered_by), "manage_roles")
            m = await resolve_member(guild, member)
            name = str(m)
            previous = m.nick
            new_nick = None if clear_nick else nickname
            await m.edit(nick=new_nick, reason=reason)
            audit_log(
                "member nick",
                {"server": server, "member": name, "from": previous, "to": new_nick},
                user=triggered_by or "",
            )
            data = {"member": name, "previous_nick": previous, "nick": new_nick}
            if new_nick is None:
                plain = f"Cleared nickname for {name}"
            else:
                plain = f"Set nickname for {name} to '{new_nick}'"
            output(ctx, data, plain_text=plain)
        return _action(client)

    run_rest(ctx, action)
