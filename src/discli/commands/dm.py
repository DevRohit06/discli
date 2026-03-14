import click

from discli.client import run_discord
from discli.utils import output


def resolve_user(client, identifier: str):
    """Resolve a user by ID or username."""
    try:
        user_id = int(identifier)
        user = client.get_user(user_id)
        if user:
            return user
    except ValueError:
        pass
    for guild in client.guilds:
        for member in guild.members:
            if member.name.lower() == identifier.lower() or str(member).lower() == identifier.lower():
                return member
    raise click.ClickException(f"User not found: {identifier}")


@click.group("dm")
def dm_group():
    """Send and read direct messages."""


@dm_group.command("send")
@click.argument("user")
@click.argument("text")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True), help="File to attach (repeatable).")
@click.pass_context
def dm_send(ctx, user, text, files):
    """Send a direct message to a user."""
    import discord

    def action(client):
        async def _action(client):
            u = resolve_user(client, user)
            dm_channel = await u.create_dm()
            attachments = [discord.File(f) for f in files]
            kwargs = {"content": text}
            if attachments:
                kwargs["files"] = attachments
            msg = await dm_channel.send(**kwargs)
            data = {
                "id": str(msg.id),
                "to": str(u),
                "to_id": str(u.id),
                "content": msg.content,
            }
            if msg.attachments:
                data["attachments"] = [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments]
            output(ctx, data, plain_text=f"Sent DM to {u} (ID: {u.id}): {text[:50]}")
        return _action(client)

    run_discord(ctx, action)


@dm_group.command("list")
@click.argument("user")
@click.option("--limit", default=10, help="Number of messages to fetch.")
@click.pass_context
def dm_list(ctx, user, limit):
    """List recent DMs with a user."""

    def action(client):
        async def _action(client):
            u = resolve_user(client, user)
            dm_channel = await u.create_dm()
            messages = []
            async for msg in dm_channel.history(limit=limit):
                messages.append({
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "author_id": str(msg.author.id),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                })
            plain_lines = []
            for m in messages:
                ts = m["timestamp"][:19].replace("T", " ")
                plain_lines.append(f"[{ts}] (msg:{m['id']}) {m['author']}: {m['content']}")
            output(ctx, messages, plain_text="\n".join(plain_lines) if plain_lines else "No DMs found.")
        return _action(client)

    run_discord(ctx, action)
