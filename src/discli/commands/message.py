import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("message")
def message_group():
    """Send, list, edit, and delete messages."""


@message_group.command("send")
@click.argument("channel")
@click.argument("text")
@click.option("--embed-title", default=None, help="Embed title.")
@click.option("--embed-desc", default=None, help="Embed description.")
@click.pass_context
def message_send(ctx, channel, text, embed_title, embed_desc):
    """Send a message to a channel."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            embed = None
            if embed_title or embed_desc:
                embed = discord.Embed(title=embed_title, description=embed_desc)
            msg = await ch.send(content=text, embed=embed)
            data = {"id": str(msg.id), "channel": ch.name, "content": msg.content}
            output(ctx, data, plain_text=f"Sent message {msg.id} to #{ch.name}")
        return _action(client)

    run_discord(ctx, action)


@message_group.command("list")
@click.argument("channel")
@click.option("--limit", default=10, help="Number of messages to fetch.")
@click.pass_context
def message_list(ctx, channel, limit):
    """List recent messages in a channel."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            messages = []
            async for msg in ch.history(limit=limit):
                messages.append({
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                })
            plain_lines = []
            for m in messages:
                ts = m["timestamp"][:19].replace("T", " ")
                plain_lines.append(f"[{ts}] {m['author']}: {m['content']}")
            output(ctx, messages, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)


@message_group.command("edit")
@click.argument("channel")
@click.argument("message_id")
@click.argument("new_text")
@click.pass_context
def message_edit(ctx, channel, message_id, new_text):
    """Edit a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.edit(content=new_text)
            output(ctx, {"id": str(msg.id), "content": new_text}, plain_text=f"Edited message {msg.id}")
        return _action(client)

    run_discord(ctx, action)


@message_group.command("delete")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def message_delete(ctx, channel, message_id):
    """Delete a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.delete()
            output(ctx, {"id": str(msg.id), "deleted": True}, plain_text=f"Deleted message {msg.id}")
        return _action(client)

    run_discord(ctx, action)


@message_group.command("get")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def message_get(ctx, channel, message_id):
    """Fetch a single message by ID."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            data = {
                "id": str(msg.id),
                "author": str(msg.author),
                "author_id": str(msg.author.id),
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "attachments": [{"filename": a.filename, "url": a.url} for a in msg.attachments],
                "embeds": [{"title": e.title, "description": e.description} for e in msg.embeds],
                "reply_to": str(msg.reference.message_id) if msg.reference else None,
            }
            plain_lines = [
                f"From: {data['author']} (ID: {data['author_id']})",
                f"At: {data['timestamp'][:19].replace('T', ' ')}",
                f"Content: {data['content']}",
            ]
            if data["attachments"]:
                plain_lines.append(f"Attachments: {', '.join(a['filename'] for a in data['attachments'])}")
            if data["reply_to"]:
                plain_lines.append(f"Reply to: {data['reply_to']}")
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)


@message_group.command("reply")
@click.argument("channel")
@click.argument("message_id")
@click.argument("text")
@click.pass_context
def message_reply(ctx, channel, message_id, text):
    """Reply to a specific message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            original = await ch.fetch_message(int(message_id))
            msg = await original.reply(content=text)
            data = {"id": str(msg.id), "channel": ch.name, "content": msg.content, "reply_to": message_id}
            output(ctx, data, plain_text=f"Replied to {message_id} in #{ch.name}")
        return _action(client)

    run_discord(ctx, action)
