import click
import discord

from discli.client import run_rest
from discli.utils import output, resolve_guild, resolve_member, resolve_role


@click.group("role")
def role_group():
    """Manage server roles."""


@role_group.command("list")
@click.argument("server")
@click.option(
    "--with-member-counts",
    is_flag=True,
    default=False,
    help=(
        "Compute per-role member counts. Off by default because it iterates the "
        "entire member list (slow on large servers, needs the Server Members intent)."
    ),
)
@click.pass_context
def role_list(ctx, server, with_member_counts):
    """List roles in a server."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            fetched_roles = await guild.fetch_roles()
            member_counts = None
            if with_member_counts:
                try:
                    member_counts = {role.id: 0 for role in fetched_roles}
                    async for member in guild.fetch_members(limit=None):
                        for member_role in member.roles:
                            if member_role.id in member_counts:
                                member_counts[member_role.id] += 1
                except discord.Forbidden:
                    # Reset to None so counts are reported as unavailable rather
                    # than silently as 0 for every role.
                    member_counts = None
            roles = [
                {
                    "id": str(role.id),
                    "name": role.name,
                    "color": str(role.color),
                    "members": member_counts.get(role.id) if member_counts is not None else None,
                }
                for role in fetched_roles
                if role.name != "@everyone"
            ]
            plain_lines = [
                f"{r['name']} (ID: {r['id']}, color: {r['color']}, "
                f"members: {r['members'] if r['members'] is not None else 'unavailable'})"
                for r in roles
            ]
            output(ctx, roles, plain_text="\n".join(plain_lines) if plain_lines else "No roles.")
        return _action(client)

    run_rest(ctx, action)


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
            guild = await resolve_guild(client, server)
            kwargs = {"name": name}
            if color:
                try:
                    kwargs["color"] = discord.Color(int(color.lstrip("#"), 16))
                except ValueError:
                    raise click.ClickException(f"Invalid color: {color} (use hex like ff0000)")
            if permissions:
                kwargs["permissions"] = discord.Permissions(int(permissions))
            role = await guild.create_role(**kwargs)
            data = {"id": str(role.id), "name": role.name}
            output(ctx, data, plain_text=f"Created role {role.name} (ID: {role.id})")
        return _action(client)

    run_rest(ctx, action)


@role_group.command("delete")
@click.argument("server")
@click.argument("role")
@click.pass_context
def role_delete(ctx, server, role):
    """Delete a role."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("role delete", f"{role} in {server}")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            r = await resolve_role(guild, role)
            name = r.name
            await r.delete()
            audit_log("role delete", {"server": server, "role": name})
            output(ctx, {"name": name, "deleted": True}, plain_text=f"Deleted role {name}")
        return _action(client)

    run_rest(ctx, action)


@role_group.command("assign")
@click.argument("server")
@click.argument("member")
@click.argument("role")
@click.pass_context
def role_assign(ctx, server, member, role):
    """Assign a role to a member."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            m = await resolve_member(guild, member)
            r = await resolve_role(guild, role)
            await m.add_roles(r)
            output(ctx, {"member": str(m), "role": r.name}, plain_text=f"Assigned {r.name} to {m}")
        return _action(client)

    run_rest(ctx, action)


@role_group.command("remove")
@click.argument("server")
@click.argument("member")
@click.argument("role")
@click.pass_context
def role_remove(ctx, server, member, role):
    """Remove a role from a member."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            m = await resolve_member(guild, member)
            r = await resolve_role(guild, role)
            await m.remove_roles(r)
            output(ctx, {"member": str(m), "role": r.name}, plain_text=f"Removed {r.name} from {m}")
        return _action(client)

    run_rest(ctx, action)


@role_group.command("edit")
@click.argument("server")
@click.argument("role")
@click.option("--name", default=None, help="New role name.")
@click.option("--color", default=None, help="New hex color.")
@click.option("--hoist/--no-hoist", default=None, help="Display separately in member list.")
@click.option("--mentionable/--no-mentionable", default=None, help="Allow @mentioning this role.")
@click.pass_context
def role_edit(ctx, server, role, name, color, hoist, mentionable):
    """Edit a role's properties."""
    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            r = await resolve_role(guild, role)
            kwargs = {}
            if name is not None:
                kwargs["name"] = name
            if color is not None:
                try:
                    kwargs["color"] = discord.Color(int(color.lstrip("#"), 16))
                except ValueError:
                    raise click.ClickException(f"Invalid color: {color} (use hex like ff0000)")
            if hoist is not None:
                kwargs["hoist"] = hoist
            if mentionable is not None:
                kwargs["mentionable"] = mentionable
            if not kwargs:
                raise click.ClickException("No changes specified.")
            await r.edit(**kwargs)
            data = {"id": str(r.id), "name": r.name, "updated": list(kwargs.keys())}
            output(ctx, data, plain_text=f"Updated role {r.name}: {', '.join(kwargs.keys())}")
        return _action(client)
    run_rest(ctx, action)
