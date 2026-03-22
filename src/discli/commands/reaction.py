import click

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("reaction")
def reaction_group():
    """Add, remove, and list reactions."""


@reaction_group.command("add")
@click.argument("channel")
@click.argument("message_id")
@click.argument("emoji")
@click.pass_context
def reaction_add(ctx, channel, message_id, emoji):
    """Add a reaction to a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
            output(ctx, {"message_id": message_id, "emoji": emoji}, plain_text=f"Reacted {emoji} to message {message_id}")
        return _action(client)

    run_discord(ctx, action)


@reaction_group.command("remove")
@click.argument("channel")
@click.argument("message_id")
@click.argument("emoji")
@click.pass_context
def reaction_remove(ctx, channel, message_id, emoji):
    """Remove a reaction from a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.remove_reaction(emoji, client.user)
            output(ctx, {"message_id": message_id, "emoji": emoji}, plain_text=f"Removed {emoji} from message {message_id}")
        return _action(client)

    run_discord(ctx, action)


@reaction_group.command("list")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def reaction_list(ctx, channel, message_id):
    """List reactions on a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            reactions = []
            for r in msg.reactions:
                reactions.append({"emoji": str(r.emoji), "count": r.count})
            plain_lines = [f"{r['emoji']} x{r['count']}" for r in reactions]
            output(ctx, reactions, plain_text="\n".join(plain_lines) if plain_lines else "No reactions.")
        return _action(client)

    run_discord(ctx, action)


@reaction_group.command("users")
@click.argument("channel")
@click.argument("message_id")
@click.argument("emoji")
@click.option("--limit", default=100, help="Max users to fetch.")
@click.pass_context
def reaction_users(ctx, channel, message_id, emoji, limit):
    """List users who reacted with a specific emoji."""
    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            target = None
            for r in msg.reactions:
                if str(r.emoji) == emoji:
                    target = r
                    break
            if not target:
                output(ctx, [], plain_text=f"No {emoji} reactions found.")
                return
            users = [u async for u in target.users(limit=limit)]
            data = [{"id": str(u.id), "name": str(u), "bot": u.bot} for u in users]
            plain_lines = [f"{u['name']} (ID: {u['id']}){' [bot]' if u['bot'] else ''}" for u in data]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)
    run_discord(ctx, action)
