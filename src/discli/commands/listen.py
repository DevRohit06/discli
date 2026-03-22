import asyncio
import json

import click
import discord


@click.command("listen")
@click.option("--server", default=None, help="Filter by server name or ID.")
@click.option("--channel", default=None, help="Filter by channel name or ID.")
@click.option("--events", default=None, help="Comma-separated event types: messages,reactions,members,edits,deletes,voice")
@click.option("--ignore-bots/--include-bots", default=True, help="Ignore messages from bots (default: ignore).")
@click.pass_context
def listen_cmd(ctx, server, channel, events, ignore_bots):
    """Listen for real-time Discord events. Ctrl+C to stop."""
    from discli.client import resolve_token
    from discli.security import is_command_allowed

    profile = ctx.obj.get("profile")
    if not is_command_allowed("listen", profile_override=profile):
        raise click.ClickException(
            "Command 'listen' is denied by your permission profile."
        )

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
        if ignore_bots and message.author.bot:
            return
        if message.guild and not should_emit(message.guild, message.channel):
            return
        mentions_bot = client.user in message.mentions if client.user else False
        attachments = [{"filename": a.filename, "url": a.url} for a in message.attachments]
        data = {
            "event": "message",
            "server": message.guild.name if message.guild else "DM",
            "server_id": str(message.guild.id) if message.guild else None,
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "channel_id": str(message.channel.id),
            "author": str(message.author),
            "author_id": str(message.author.id),
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "message_id": str(message.id),
            "mentions_bot": mentions_bot,
            "attachments": attachments,
            "reply_to": str(message.reference.message_id) if message.reference else None,
        }
        ts = data["timestamp"][:19].replace("T", " ")
        mention_tag = " @BOT" if mentions_bot else ""
        attach_tag = f" [{len(attachments)} file(s)]" if attachments else ""
        reply_tag = f" (reply to {data['reply_to']})" if data["reply_to"] else ""
        plain = f"[{ts}] (msg:{data['message_id']}) {data['author']} (uid:{data['author_id']}) in #{data['channel']} (ch:{data['channel_id']}): {data['content']}{mention_tag}{attach_tag}{reply_tag}"
        emit(data, plain)

    @client.event
    async def on_message_edit(before, after):
        if event_filter and "edits" not in event_filter:
            return
        if ignore_bots and after.author.bot:
            return
        if after.guild and not should_emit(after.guild, after.channel):
            return
        data = {
            "event": "message_edit",
            "server": after.guild.name if after.guild else "DM",
            "server_id": str(after.guild.id) if after.guild else None,
            "channel": after.channel.name if hasattr(after.channel, "name") else "DM",
            "channel_id": str(after.channel.id),
            "author": str(after.author),
            "author_id": str(after.author.id),
            "message_id": str(after.id),
            "old_content": before.content if before.content else None,
            "new_content": after.content,
            "timestamp": after.edited_at.isoformat() if after.edited_at else after.created_at.isoformat(),
        }
        ts = data["timestamp"][:19].replace("T", " ")
        plain = f"[{ts}] EDIT (msg:{data['message_id']}) {data['author']} in #{data['channel']}: {data['old_content']} -> {data['new_content']}"
        emit(data, plain)

    @client.event
    async def on_message_delete(message):
        if event_filter and "deletes" not in event_filter:
            return
        if message.guild and not should_emit(message.guild, message.channel):
            return
        data = {
            "event": "message_delete",
            "server": message.guild.name if message.guild else "DM",
            "server_id": str(message.guild.id) if message.guild else None,
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "channel_id": str(message.channel.id),
            "author": str(message.author) if message.author else "unknown",
            "author_id": str(message.author.id) if message.author else None,
            "message_id": str(message.id),
            "content": message.content if message.content else None,
        }
        plain = f"DELETE (msg:{data['message_id']}) {data['author']} in #{data['channel']}: {data['content']}"
        emit(data, plain)

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
            "channel_id": str(reaction.message.channel.id),
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
            "user_id": str(user.id),
        }
        emit(data, f"{data['user']} (uid:{data['user_id']}) reacted {data['emoji']} on msg:{data['message_id']} in #{data['channel']}")

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
            "channel_id": str(reaction.message.channel.id),
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
            "user_id": str(user.id),
        }
        emit(data, f"{data['user']} (uid:{data['user_id']}) removed {data['emoji']} from msg:{data['message_id']} in #{data['channel']}")

    @client.event
    async def on_member_join(member):
        if event_filter and "members" not in event_filter:
            return
        data = {
            "event": "member_join",
            "server": member.guild.name,
            "member": str(member),
            "member_id": str(member.id),
        }
        emit(data, f"{data['member']} (uid:{data['member_id']}) joined {data['server']}")

    @client.event
    async def on_member_remove(member):
        if event_filter and "members" not in event_filter:
            return
        data = {
            "event": "member_remove",
            "server": member.guild.name,
            "member": str(member),
            "member_id": str(member.id),
        }
        emit(data, f"{data['member']} (uid:{data['member_id']}) left {data['server']}")

    @client.event
    async def on_voice_state_update(member, before, after):
        if event_filter and "voice" not in event_filter:
            return
        if before.channel is None and after.channel is None:
            return
        event_data = {
            "event": "voice_state",
            "server": member.guild.name,
            "server_id": str(member.guild.id),
            "member": str(member),
            "member_id": str(member.id),
        }
        if before.channel is None and after.channel is not None:
            event_data["action"] = "joined"
            event_data["channel"] = after.channel.name
            event_data["channel_id"] = str(after.channel.id)
            plain = f"{member} joined voice #{after.channel.name}"
        elif before.channel is not None and after.channel is None:
            event_data["action"] = "left"
            event_data["channel"] = before.channel.name
            event_data["channel_id"] = str(before.channel.id)
            plain = f"{member} left voice #{before.channel.name}"
        elif before.channel != after.channel:
            event_data["action"] = "moved"
            event_data["from_channel"] = before.channel.name
            event_data["from_channel_id"] = str(before.channel.id)
            event_data["channel"] = after.channel.name
            event_data["channel_id"] = str(after.channel.id)
            plain = f"{member} moved from #{before.channel.name} to #{after.channel.name}"
        else:
            event_data["action"] = "updated"
            event_data["channel"] = after.channel.name if after.channel else None
            plain = f"{member} voice state updated in #{after.channel.name if after.channel else '?'}"
        emit(event_data, plain)

    try:
        asyncio.run(client.start(token))
    except KeyboardInterrupt:
        click.echo("\nStopped listening.", err=True)
