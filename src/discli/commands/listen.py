import asyncio
import json

import click
import discord


@click.command("listen")
@click.option("--server", default=None, help="Filter by server name or ID.")
@click.option("--channel", default=None, help="Filter by channel name or ID.")
@click.option("--events", default=None, help="Comma-separated event types: messages,reactions,members")
@click.pass_context
def listen_cmd(ctx, server, channel, events):
    """Listen for real-time Discord events. Ctrl+C to stop."""
    from discli.client import resolve_token

    token = resolve_token(ctx.obj.get("token"), {})
    use_json = ctx.obj.get("use_json", False)
    event_filter = set(events.split(",")) if events else None

    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    def should_emit(guild, ch):
        if server:
            try:
                if str(guild.id) != server and guild.name.lower() != server.lower():
                    return False
            except Exception:
                return False
        if channel:
            ch_name = channel.lstrip("#")
            try:
                if str(ch.id) != ch_name and ch.name != ch_name:
                    return False
            except Exception:
                return False
        return True

    def emit(data, plain):
        if use_json:
            click.echo(json.dumps(data, default=str))
        else:
            click.echo(plain)

    @client.event
    async def on_ready():
        click.echo(f"Listening as {client.user}... (Ctrl+C to stop)", err=True)

    @client.event
    async def on_message(message):
        if event_filter and "messages" not in event_filter:
            return
        if not should_emit(message.guild, message.channel):
            return
        data = {
            "event": "message",
            "server": message.guild.name if message.guild else "DM",
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "author": str(message.author),
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "message_id": str(message.id),
        }
        emit(data, f"[{data['timestamp'][:19]}] #{data['channel']} {data['author']}: {data['content']}")

    @client.event
    async def on_reaction_add(reaction, user):
        if event_filter and "reactions" not in event_filter:
            return
        if not should_emit(reaction.message.guild, reaction.message.channel):
            return
        data = {
            "event": "reaction_add",
            "server": reaction.message.guild.name,
            "channel": reaction.message.channel.name,
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
        }
        emit(data, f"{data['user']} reacted {data['emoji']} on message {data['message_id']} in #{data['channel']}")

    @client.event
    async def on_reaction_remove(reaction, user):
        if event_filter and "reactions" not in event_filter:
            return
        if not should_emit(reaction.message.guild, reaction.message.channel):
            return
        data = {
            "event": "reaction_remove",
            "server": reaction.message.guild.name,
            "channel": reaction.message.channel.name,
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
        }
        emit(data, f"{data['user']} removed {data['emoji']} from message {data['message_id']} in #{data['channel']}")

    @client.event
    async def on_member_join(member):
        if event_filter and "members" not in event_filter:
            return
        data = {"event": "member_join", "server": member.guild.name, "member": str(member)}
        emit(data, f"{data['member']} joined {data['server']}")

    @client.event
    async def on_member_remove(member):
        if event_filter and "members" not in event_filter:
            return
        data = {"event": "member_remove", "server": member.guild.name, "member": str(member)}
        emit(data, f"{data['member']} left {data['server']}")

    try:
        asyncio.run(client.start(token))
    except KeyboardInterrupt:
        click.echo("\nStopped listening.", err=True)
