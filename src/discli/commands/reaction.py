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
