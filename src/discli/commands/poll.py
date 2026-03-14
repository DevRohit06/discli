import datetime

import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("poll")
def poll_group():
    """Create and manage polls."""


@poll_group.command("create")
@click.argument("channel")
@click.argument("question")
@click.argument("answers", nargs=-1, required=True)
@click.option("--duration", default=24, type=int, help="Poll duration in hours (default: 24).")
@click.option("--multiple", is_flag=True, default=False, help="Allow multiple selections.")
@click.option("--emoji", "-e", multiple=True, help="Emoji for each answer (in order). Use once per answer.")
@click.pass_context
def poll_create(ctx, channel, question, answers, duration, multiple, emoji):
    """Create a poll in a channel.

    CHANNEL is the channel name or ID.
    QUESTION is the poll question.
    ANSWERS are the poll options (at least 2).

    Examples:
      discli poll create #general "Favorite AI?" Claude Gemini ChatGPT
      discli poll create #general "Best?" A B C -e 🅰️ -e 🅱️ -e ©️
      discli poll create #general "Vote!" Yes No --multiple -e ✅ -e ❌
    """
    if len(answers) < 2:
        raise click.ClickException("A poll needs at least 2 answers.")

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            poll = discord.Poll(
                question=question,
                duration=datetime.timedelta(hours=duration),
                multiple=multiple,
            )
            for i, answer in enumerate(answers):
                answer_emoji = emoji[i] if i < len(emoji) else None
                poll.add_answer(text=answer, emoji=answer_emoji)
            msg = await ch.send(poll=poll)
            data = {
                "message_id": str(msg.id),
                "channel": ch.name,
                "channel_id": str(ch.id),
                "question": question,
                "answers": list(answers),
                "duration_hours": duration,
                "multiple": multiple,
            }
            if emoji:
                data["emojis"] = list(emoji)
            output(ctx, data, plain_text=f"Poll created in #{ch.name} (message {msg.id}): {question}")
        return _action(client)

    run_discord(ctx, action)
