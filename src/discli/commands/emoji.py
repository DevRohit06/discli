import click

from discli.client import run_rest
from discli.utils import output, resolve_guild, resolve_role

# Discord rejects emoji images larger than 256 KB. Checking locally turns an
# opaque 400 into an actionable message before the upload is attempted.
MAX_EMOJI_BYTES = 256 * 1024


@click.group("emoji")
def emoji_group():
    """Manage custom server emoji."""


def _serialize(emoji) -> dict:
    return {
        "id": str(emoji.id),
        "name": emoji.name,
        # The form you paste into a message or pass to 'discli reaction add'.
        "mention": str(emoji),
        "animated": emoji.animated,
        "available": emoji.available,
        "managed": emoji.managed,
        "url": emoji.url,
    }


async def _resolve_emoji(guild, identifier: str):
    """Resolve a guild emoji by ID or name."""
    emojis = await guild.fetch_emojis()
    matches = [e for e in emojis if str(e.id) == identifier]
    if not matches:
        normalized = identifier.strip(":").casefold()
        matches = [e for e in emojis if e.name.casefold() == normalized]
    if not matches:
        raise click.ClickException(f"Emoji not found in {guild.name}: {identifier}")
    if len(matches) > 1:
        ids = ", ".join(str(e.id) for e in matches)
        raise click.ClickException(
            f"Multiple emoji match '{identifier}' (IDs: {ids}). Use an ID."
        )
    return matches[0]


@emoji_group.command("list")
@click.argument("server")
@click.pass_context
def emoji_list(ctx, server):
    """List custom emoji in a server."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            emojis = [_serialize(e) for e in await guild.fetch_emojis()]
            plain_lines = [
                f"{e['mention']} {e['name']} (ID: {e['id']}"
                + (", animated" if e["animated"] else "")
                + ")"
                for e in emojis
            ]
            output(ctx, emojis, plain_text="\n".join(plain_lines) if plain_lines else "No custom emoji.")
        return _action(client)

    run_rest(ctx, action)


@emoji_group.command("upload")
@click.argument("server")
@click.argument("name")
@click.argument("image", type=click.Path(exists=True))
@click.option("--role", "roles", multiple=True, help="Restrict use to this role (repeatable).")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def emoji_upload(ctx, server, name, image, roles, reason):
    """Upload a custom emoji from an image file.

    Needs the Create Expressions permission, which Discord split out of
    Manage Expressions in February 2026.
    """
    from discli.security import audit_log

    with open(image, "rb") as fh:
        payload = fh.read()
    if len(payload) > MAX_EMOJI_BYTES:
        raise click.ClickException(
            f"Emoji images must be 256 KB or smaller; {image} is {len(payload) / 1024:.0f} KB."
        )

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            kwargs = {"name": name, "image": payload, "reason": reason}
            if roles:
                kwargs["roles"] = [await resolve_role(guild, r) for r in roles]
            emoji = await guild.create_custom_emoji(**kwargs)
            data = _serialize(emoji)
            audit_log("emoji upload", {"server": server, "name": name, "id": data["id"]})
            output(ctx, data, plain_text=f"Uploaded emoji {data['mention']} (ID: {data['id']})")
        return _action(client)

    run_rest(ctx, action)


@emoji_group.command("rename")
@click.argument("server")
@click.argument("emoji")
@click.argument("new_name")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def emoji_rename(ctx, server, emoji, new_name, reason):
    """Rename a custom emoji."""
    from discli.security import audit_log

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            target = await _resolve_emoji(guild, emoji)
            previous = target.name
            updated = await target.edit(name=new_name, reason=reason)
            data = _serialize(updated or target)
            data["previous_name"] = previous
            audit_log("emoji rename", {"server": server, "from": previous, "to": new_name})
            output(ctx, data, plain_text=f"Renamed emoji '{previous}' to '{new_name}'")
        return _action(client)

    run_rest(ctx, action)


@emoji_group.command("delete")
@click.argument("server")
@click.argument("emoji")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def emoji_delete(ctx, server, emoji, reason):
    """Delete a custom emoji."""
    from discli.security import audit_log, confirm_destructive
    confirm_destructive("emoji delete", f"emoji {emoji} in {server}")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            target = await _resolve_emoji(guild, emoji)
            name, emoji_id = target.name, str(target.id)
            await target.delete(reason=reason)
            audit_log("emoji delete", {"server": server, "name": name, "id": emoji_id})
            output(ctx, {"id": emoji_id, "name": name, "deleted": True}, plain_text=f"Deleted emoji '{name}'")
        return _action(client)

    run_rest(ctx, action)
