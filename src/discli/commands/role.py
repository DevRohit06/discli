import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_guild


def resolve_role(guild, identifier: str):
    try:
        role_id = int(identifier)
        role = guild.get_role(role_id)
        if role:
            return role
    except ValueError:
        pass
    for role in guild.roles:
        if role.name.lower() == identifier.lower():
            return role
    raise click.ClickException(f"Role not found: {identifier}")


def resolve_member(guild, identifier: str):
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


@click.group("role")
def role_group():
    """Manage server roles."""


@role_group.command("list")
@click.argument("server")
@click.pass_context
def role_list(ctx, server):
    """List roles in a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            roles = [{"id": str(r.id), "name": r.name, "color": str(r.color), "members": len(r.members)} for r in guild.roles if r.name != "@everyone"]
            plain_lines = [f"{r['name']} (ID: {r['id']}, color: {r['color']}, members: {r['members']})" for r in roles]
            output(ctx, roles, plain_text="\n".join(plain_lines) if plain_lines else "No roles.")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("create")
@click.argument("server")
@click.argument("name")
@click.option("--color", default=None, help="Hex color (e.g. ff0000).")
@click.option("--permissions", default=None, help="Permission integer.")
@click.pass_context
def role_create(ctx, server, name, color, permissions):
    """Create a role."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            kwargs = {"name": name}
            if color:
                kwargs["color"] = discord.Color(int(color, 16))
            if permissions:
                kwargs["permissions"] = discord.Permissions(int(permissions))
            role = await guild.create_role(**kwargs)
            data = {"id": str(role.id), "name": role.name}
            output(ctx, data, plain_text=f"Created role {role.name} (ID: {role.id})")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("delete")
@click.argument("server")
@click.argument("role")
@click.pass_context
def role_delete(ctx, server, role):
    """Delete a role."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            r = resolve_role(guild, role)
            name = r.name
            await r.delete()
            output(ctx, {"name": name, "deleted": True}, plain_text=f"Deleted role {name}")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("assign")
@click.argument("server")
@click.argument("member")
@click.argument("role")
@click.pass_context
def role_assign(ctx, server, member, role):
    """Assign a role to a member."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            r = resolve_role(guild, role)
            await m.add_roles(r)
            output(ctx, {"member": str(m), "role": r.name}, plain_text=f"Assigned {r.name} to {m}")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("remove")
@click.argument("server")
@click.argument("member")
@click.argument("role")
@click.pass_context
def role_remove(ctx, server, member, role):
    """Remove a role from a member."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            r = resolve_role(guild, role)
            await m.remove_roles(r)
            output(ctx, {"member": str(m), "role": r.name}, plain_text=f"Removed {r.name} from {m}")
        return _action(client)

    run_discord(ctx, action)
