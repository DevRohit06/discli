import click
import discord

from discli.client import run_rest
from discli.utils import output, resolve_channel


@click.group("webhook")
def webhook_group():
    """Manage webhooks."""


async def _resolve_webhook(ch, identifier: str):
    """Resolve a webhook in a channel by ID or name.

    Webhooks fetched this way carry their token, so the returned object can
    send messages without a separate URL.
    """
    webhooks = await ch.webhooks()
    matches = [w for w in webhooks if str(w.id) == identifier]
    if not matches:
        matches = [w for w in webhooks if (w.name or "").casefold() == identifier.casefold()]
    if not matches:
        raise click.ClickException(f"Webhook not found: {identifier}")
    if len(matches) > 1:
        ids = ", ".join(str(w.id) for w in matches)
        raise click.ClickException(
            f"Multiple webhooks match '{identifier}' (IDs: {ids}). Use an ID."
        )
    return matches[0]


@webhook_group.command("list")
@click.argument("channel")
@click.pass_context
def webhook_list(ctx, channel):
    """List webhooks in a channel."""
    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            webhooks = await ch.webhooks()
            data = [{"id": str(w.id), "name": w.name, "url": w.url} for w in webhooks]
            plain_lines = [f"{w['name']} (ID: {w['id']})" for w in data]
            output(ctx, data, plain_text="\n".join(plain_lines) if plain_lines else "No webhooks.")
        return _action(client)
    run_rest(ctx, action)


@webhook_group.command("create")
@click.argument("channel")
@click.argument("name")
@click.pass_context
def webhook_create(ctx, channel, name):
    """Create a webhook in a channel."""
    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            webhook = await ch.create_webhook(name=name)
            data = {"id": str(webhook.id), "name": webhook.name, "url": webhook.url}
            output(ctx, data, plain_text=f"Created webhook '{webhook.name}' (URL: {webhook.url})")
        return _action(client)
    run_rest(ctx, action)


@webhook_group.command("send")
@click.argument("channel")
@click.argument("webhook")
@click.argument("text")
@click.option("--username", default=None, help="Override the display name for this message.")
@click.option("--avatar-url", default=None, help="Override the avatar for this message.")
@click.option("--thread", default=None, help="Thread ID to post into.")
@click.option("--embed-title", default=None, help="Embed title.")
@click.option("--embed-desc", default=None, help="Embed description.")
@click.option("--embed-color", default=None, help="Embed color (hex like ff0000).")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True), help="File to attach (repeatable).")
@click.pass_context
def webhook_send(ctx, channel, webhook, text, username, avatar_url, thread, embed_title, embed_desc, embed_color, files):
    """Send a message through a webhook, optionally under a custom identity."""
    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            target = await _resolve_webhook(ch, webhook)

            embed = None
            if any([embed_title, embed_desc, embed_color]):
                embed_kwargs = {}
                if embed_title:
                    embed_kwargs["title"] = embed_title
                if embed_desc:
                    embed_kwargs["description"] = embed_desc
                if embed_color:
                    try:
                        embed_kwargs["color"] = discord.Color(int(embed_color.lstrip("#"), 16))
                    except ValueError:
                        raise click.ClickException(f"Invalid embed color: {embed_color} (use hex like ff0000)")
                embed = discord.Embed(**embed_kwargs)

            kwargs = {"content": text, "wait": True}
            if username:
                kwargs["username"] = username
            if avatar_url:
                kwargs["avatar_url"] = avatar_url
            if embed is not None:
                kwargs["embed"] = embed
            if files:
                kwargs["files"] = [discord.File(f) for f in files]
            if thread:
                kwargs["thread"] = discord.Object(id=int(thread))

            msg = await target.send(**kwargs)
            data = {
                "id": str(msg.id),
                "webhook": target.name,
                "webhook_id": str(target.id),
                "channel": getattr(ch, "name", None),
                "content": msg.content,
                "username": username or target.name,
            }
            output(ctx, data, plain_text=f"Sent message {msg.id} via webhook '{target.name}'")
        return _action(client)
    run_rest(ctx, action)


@webhook_group.command("delete")
@click.argument("channel")
@click.argument("webhook_id")
@click.pass_context
def webhook_delete(ctx, channel, webhook_id):
    """Delete a webhook."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("webhook delete", f"webhook {webhook_id}")

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            target = await _resolve_webhook(ch, webhook_id)
            name = target.name
            await target.delete()
            audit_log("webhook delete", {"channel": channel, "webhook_id": webhook_id})
            output(ctx, {"id": webhook_id, "deleted": True}, plain_text=f"Deleted webhook '{name}'")
        return _action(client)
    run_rest(ctx, action)
