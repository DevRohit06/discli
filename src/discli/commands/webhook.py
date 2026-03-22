import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("webhook")
def webhook_group():
    """Manage webhooks."""


@webhook_group.command("list")
@click.argument("channel")
@click.pass_context
def webhook_list(ctx, channel):
    """List webhooks in a channel."""
    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            webhooks = await ch.webhooks()
            data = [{"id": str(w.id), "name": w.name, "url": w.url} for w in webhooks]
            plain_lines = [f"{w['name']} (ID: {w['id']})" for w in data]
            output(ctx, data, plain_text="\n".join(plain_lines) if plain_lines else "No webhooks.")
        return _action(client)
    run_discord(ctx, action)


@webhook_group.command("create")
@click.argument("channel")
@click.argument("name")
@click.pass_context
def webhook_create(ctx, channel, name):
    """Create a webhook in a channel."""
    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            webhook = await ch.create_webhook(name=name)
            data = {"id": str(webhook.id), "name": webhook.name, "url": webhook.url}
            output(ctx, data, plain_text=f"Created webhook '{webhook.name}' (URL: {webhook.url})")
        return _action(client)
    run_discord(ctx, action)


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
            ch = resolve_channel(client, channel)
            webhooks = await ch.webhooks()
            target = None
            for w in webhooks:
                if str(w.id) == webhook_id:
                    target = w
                    break
            if not target:
                raise click.ClickException(f"Webhook not found: {webhook_id}")
            name = target.name
            await target.delete()
            audit_log("webhook delete", {"channel": channel, "webhook_id": webhook_id})
            output(ctx, {"id": webhook_id, "deleted": True}, plain_text=f"Deleted webhook '{name}'")
        return _action(client)
    run_discord(ctx, action)
