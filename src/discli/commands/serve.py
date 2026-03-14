"""discli serve — persistent bidirectional Discord bot process.

Events go out on stdout as JSONL.
Commands come in on stdin as JSONL.
"""

import asyncio
import json
import sys
import time
import uuid

import click
import discord
from discord import app_commands

DISCORD_MSG_LIMIT = 2000
STREAM_EDIT_INTERVAL = 1.5  # Discord rate limit on edits
CODE_BLOCK_FILE_THRESHOLD = 800


@click.command("serve")
@click.option("--server", default=None, help="Filter events by server name or ID.")
@click.option("--channel", default=None, help="Filter events by channel name or ID.")
@click.option("--events", default=None, help="Comma-separated event types: messages,reactions,members,edits,deletes")
@click.option("--include-self/--no-include-self", default=True, help="Include bot's own messages in events (default: include).")
@click.option("--slash-commands", "slash_commands_file", default=None, type=click.Path(exists=True),
              help="JSON file defining slash commands to register.")
@click.option("--status", default="online", type=click.Choice(["online", "idle", "dnd", "invisible"]),
              help="Bot status on connect.")
@click.option("--activity", default=None, help="Activity type: playing, watching, listening, competing.")
@click.option("--activity-text", default=None, help="Activity text.")
@click.pass_context
def serve_cmd(ctx, server, channel, events, include_self, slash_commands_file,
              status, activity, activity_text):
    """Start a persistent bot process with bidirectional JSONL communication."""
    from discli.client import resolve_token
    from discli.security import is_command_allowed

    profile = ctx.obj.get("profile")
    if not is_command_allowed("serve", profile_override=profile):
        raise click.ClickException("Command 'serve' is denied by your permission profile.")

    token = resolve_token(ctx.obj.get("token"), {})
    event_filter = set(events.split(",")) if events else None

    # Load slash command definitions
    slash_defs = []
    if slash_commands_file:
        with open(slash_commands_file) as f:
            slash_defs = json.load(f)

    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    # State
    typing_tasks: dict[str, asyncio.Task] = {}  # channel_id -> task
    streams: dict[str, dict] = {}  # stream_id -> stream state
    interactions: dict[str, discord.Interaction] = {}  # token -> interaction

    # ── Helpers ──────────────────────────────────────────────────────

    def emit(data: dict) -> None:
        """Write JSONL to stdout."""
        try:
            sys.stdout.write(json.dumps(data, default=str) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            raise SystemExit(0)

    def should_emit(guild, ch) -> bool:
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

    def resolve_channel_by_id(channel_id: str):
        return client.get_channel(int(channel_id))

    # ── Discord Events → stdout ─────────────────────────────────────

    @client.event
    async def on_ready():
        # Emit ready as soon as the gateway connection is established.
        # This follows Discord's standard: on_ready means connected,
        # slash command sync is a separate (slow) API call.
        emit({
            "event": "ready",
            "bot_id": str(client.user.id),
            "bot_name": str(client.user),
        })
        # Set presence
        await _set_presence(status, activity, activity_text)
        # Start stdin reader
        asyncio.create_task(_stdin_reader())
        # Sync slash commands (Discord API call, can take seconds)
        if slash_defs:
            await _register_slash_commands()

    @client.event
    async def on_message(message):
        if event_filter and "messages" not in event_filter:
            return
        if not include_self and message.author == client.user:
            return
        if message.author.bot and message.author != client.user:
            return
        if message.guild and not should_emit(message.guild, message.channel):
            return
        mentions_bot = client.user in message.mentions if client.user else False
        is_dm = not message.guild
        emit({
            "event": "message",
            "server": message.guild.name if message.guild else None,
            "server_id": str(message.guild.id) if message.guild else None,
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "channel_id": str(message.channel.id),
            "author": str(message.author),
            "author_id": str(message.author.id),
            "is_bot": message.author.bot,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "message_id": str(message.id),
            "mentions_bot": mentions_bot,
            "is_dm": is_dm,
            "attachments": [{"filename": a.filename, "url": a.url, "size": a.size} for a in message.attachments],
            "reply_to": str(message.reference.message_id) if message.reference else None,
        })

    @client.event
    async def on_message_edit(before, after):
        if event_filter and "edits" not in event_filter:
            return
        if after.author.bot:
            return
        if after.guild and not should_emit(after.guild, after.channel):
            return
        emit({
            "event": "message_edit",
            "server": after.guild.name if after.guild else None,
            "server_id": str(after.guild.id) if after.guild else None,
            "channel": after.channel.name if hasattr(after.channel, "name") else "DM",
            "channel_id": str(after.channel.id),
            "author": str(after.author),
            "author_id": str(after.author.id),
            "message_id": str(after.id),
            "old_content": before.content if before.content else None,
            "new_content": after.content,
            "timestamp": (after.edited_at or after.created_at).isoformat(),
        })

    @client.event
    async def on_message_delete(message):
        if event_filter and "deletes" not in event_filter:
            return
        if message.guild and not should_emit(message.guild, message.channel):
            return
        emit({
            "event": "message_delete",
            "server": message.guild.name if message.guild else None,
            "server_id": str(message.guild.id) if message.guild else None,
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "channel_id": str(message.channel.id),
            "author": str(message.author) if message.author else None,
            "author_id": str(message.author.id) if message.author else None,
            "message_id": str(message.id),
            "content": message.content if message.content else None,
        })

    @client.event
    async def on_reaction_add(reaction, user):
        if event_filter and "reactions" not in event_filter:
            return
        if reaction.message.guild and not should_emit(reaction.message.guild, reaction.message.channel):
            return
        emit({
            "event": "reaction_add",
            "server": reaction.message.guild.name if reaction.message.guild else None,
            "channel": reaction.message.channel.name,
            "channel_id": str(reaction.message.channel.id),
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
            "user_id": str(user.id),
        })

    @client.event
    async def on_reaction_remove(reaction, user):
        if event_filter and "reactions" not in event_filter:
            return
        if reaction.message.guild and not should_emit(reaction.message.guild, reaction.message.channel):
            return
        emit({
            "event": "reaction_remove",
            "server": reaction.message.guild.name if reaction.message.guild else None,
            "channel": reaction.message.channel.name,
            "channel_id": str(reaction.message.channel.id),
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
            "user_id": str(user.id),
        })

    @client.event
    async def on_member_join(member):
        if event_filter and "members" not in event_filter:
            return
        emit({
            "event": "member_join",
            "server": member.guild.name,
            "server_id": str(member.guild.id),
            "member": str(member),
            "member_id": str(member.id),
        })

    @client.event
    async def on_member_remove(member):
        if event_filter and "members" not in event_filter:
            return
        emit({
            "event": "member_remove",
            "server": member.guild.name,
            "server_id": str(member.guild.id),
            "member": str(member),
            "member_id": str(member.id),
        })

    # ── Slash Commands ──────────────────────────────────────────────

    async def _register_slash_commands():
        for cmd_def in slash_defs:
            name = cmd_def["name"]
            desc = cmd_def.get("description", name)
            params = cmd_def.get("params", [])

            if params:
                # Command with a single string parameter
                param = params[0]

                @tree.command(name=name, description=desc)
                @app_commands.describe(**{param["name"]: param.get("description", param["name"])})
                async def slash_handler(interaction: discord.Interaction, **kwargs):
                    cmd_name = interaction.command.name
                    itk = str(uuid.uuid4())
                    interactions[itk] = interaction
                    await interaction.response.defer(thinking=True)
                    emit({
                        "event": "slash_command",
                        "command": cmd_name,
                        "args": {k: str(v) for k, v in kwargs.items()},
                        "channel_id": str(interaction.channel_id),
                        "user": str(interaction.user),
                        "user_id": str(interaction.user.id),
                        "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
                        "interaction_token": itk,
                    })
            else:
                @tree.command(name=name, description=desc)
                async def slash_handler_no_args(interaction: discord.Interaction):
                    cmd_name = interaction.command.name
                    itk = str(uuid.uuid4())
                    interactions[itk] = interaction
                    await interaction.response.defer(thinking=True)
                    emit({
                        "event": "slash_command",
                        "command": cmd_name,
                        "args": {},
                        "channel_id": str(interaction.channel_id),
                        "user": str(interaction.user),
                        "user_id": str(interaction.user.id),
                        "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
                        "interaction_token": itk,
                    })

        await tree.sync()
        emit({"event": "slash_commands_synced", "count": len(slash_defs)})

    # ── Presence ────────────────────────────────────────────────────

    async def _set_presence(status_str: str, activity_type: str | None, activity_text: str | None):
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        activity_obj = None
        if activity_type and activity_text:
            type_map = {
                "playing": discord.ActivityType.playing,
                "watching": discord.ActivityType.watching,
                "listening": discord.ActivityType.listening,
                "competing": discord.ActivityType.competing,
            }
            at = type_map.get(activity_type)
            if at:
                activity_obj = discord.Activity(type=at, name=activity_text)

        await client.change_presence(
            status=status_map.get(status_str, discord.Status.online),
            activity=activity_obj,
        )

    # ── Typing Management ──────────────────────────────────────────

    async def _typing_loop(channel_id: str):
        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return
        try:
            async with ch.typing():
                while True:
                    await asyncio.sleep(8)
        except asyncio.CancelledError:
            pass

    def _start_typing(channel_id: str):
        if channel_id in typing_tasks and not typing_tasks[channel_id].done():
            return  # already typing
        typing_tasks[channel_id] = asyncio.create_task(_typing_loop(channel_id))

    def _stop_typing(channel_id: str):
        task = typing_tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()

    # ── Streaming Edits ────────────────────────────────────────────

    async def _stream_flush_loop(stream_id: str):
        """Flush buffered content to Discord every STREAM_EDIT_INTERVAL seconds."""
        try:
            while True:
                await asyncio.sleep(STREAM_EDIT_INTERVAL)
                stream = streams.get(stream_id)
                if not stream or stream.get("done"):
                    break
                await _stream_flush(stream_id)
        except asyncio.CancelledError:
            pass

    async def _stream_flush(stream_id: str):
        stream = streams.get(stream_id)
        if not stream:
            return
        content = stream["buffer"]
        if content == stream.get("last_flushed"):
            return  # nothing new
        msg = stream.get("message")
        if not msg:
            return
        # Truncate to Discord limit
        display = content[:DISCORD_MSG_LIMIT] if len(content) > DISCORD_MSG_LIMIT else content
        try:
            await msg.edit(content=display or "...")
            stream["last_flushed"] = content
        except discord.HTTPException:
            pass

    async def _handle_stream_start(cmd: dict) -> dict:
        channel_id = cmd.get("channel_id")
        reply_to = cmd.get("reply_to")
        interaction_token = cmd.get("interaction_token")
        stream_id = str(uuid.uuid4())[:8]

        ch = resolve_channel_by_id(channel_id)

        msg = None
        if interaction_token and interaction_token in interactions:
            # Respond to slash command interaction
            interaction = interactions[interaction_token]
            try:
                await interaction.followup.send("...")
                # Get the followup message
                msg = (await interaction.original_response()) if not interaction.response.is_done() else None
                # For followups, we need to fetch differently
                async for m in ch.history(limit=1):
                    if m.author == client.user:
                        msg = m
                        break
            except discord.HTTPException:
                if ch:
                    msg = await ch.send("...")
        elif ch:
            if reply_to:
                try:
                    original = await ch.fetch_message(int(reply_to))
                    msg = await original.reply("...")
                except discord.HTTPException:
                    msg = await ch.send("...")
            else:
                msg = await ch.send("...")

        if not msg:
            return {"error": "Failed to start stream"}

        # Stop typing for this channel
        _stop_typing(channel_id)

        streams[stream_id] = {
            "message": msg,
            "channel_id": channel_id,
            "buffer": "",
            "last_flushed": None,
            "done": False,
        }

        # Start periodic flush task
        asyncio.create_task(_stream_flush_loop(stream_id))

        return {"stream_id": stream_id, "message_id": str(msg.id)}

    async def _handle_stream_chunk(cmd: dict) -> dict:
        stream_id = cmd.get("stream_id")
        content = cmd.get("content", "")
        stream = streams.get(stream_id)
        if not stream:
            return {"error": f"Unknown stream: {stream_id}"}
        stream["buffer"] += content
        return {"ok": True}

    async def _handle_stream_end(cmd: dict) -> dict:
        stream_id = cmd.get("stream_id")
        stream = streams.get(stream_id)
        if not stream:
            return {"error": f"Unknown stream: {stream_id}"}
        stream["done"] = True

        # Final flush
        msg = stream["message"]
        content = stream["buffer"]

        if len(content) <= DISCORD_MSG_LIMIT:
            try:
                await msg.edit(content=content or "(empty response)")
            except discord.HTTPException:
                pass
        else:
            # Split into multiple messages for overflow
            try:
                await msg.edit(content=content[:DISCORD_MSG_LIMIT])
            except discord.HTTPException:
                pass
            ch = resolve_channel_by_id(stream["channel_id"])
            if ch:
                remaining = content[DISCORD_MSG_LIMIT:]
                while remaining:
                    chunk = remaining[:DISCORD_MSG_LIMIT]
                    remaining = remaining[DISCORD_MSG_LIMIT:]
                    try:
                        await ch.send(chunk)
                    except discord.HTTPException:
                        break

        message_id = str(msg.id)
        streams.pop(stream_id, None)
        return {"ok": True, "message_id": message_id}

    # ── stdin Command Dispatch ─────────────────────────────────────

    async def _stdin_reader():
        """Read JSONL commands from stdin and dispatch."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    # stdin closed — shut down
                    await client.close()
                    return
                line = line.decode().strip()
                if not line:
                    continue
                try:
                    cmd = json.loads(line)
                except json.JSONDecodeError:
                    emit({"event": "error", "message": f"Invalid JSON: {line[:100]}"})
                    continue

                req_id = cmd.get("req_id")
                result = await _dispatch(cmd)
                if req_id is not None:
                    result["req_id"] = req_id
                result["event"] = "response"
                emit(result)

            except asyncio.CancelledError:
                return
            except Exception as e:
                emit({"event": "error", "message": str(e)})

    async def _dispatch(cmd: dict) -> dict:
        action = cmd.get("action")
        if not action:
            return {"error": "Missing 'action' field"}

        try:
            if action == "send":
                return await _action_send(cmd)
            elif action == "reply":
                return await _action_reply(cmd)
            elif action == "edit":
                return await _action_edit(cmd)
            elif action == "delete":
                return await _action_delete(cmd)
            elif action == "typing_start":
                _start_typing(cmd["channel_id"])
                return {"ok": True}
            elif action == "typing_stop":
                _stop_typing(cmd["channel_id"])
                return {"ok": True}
            elif action == "presence":
                await _set_presence(
                    cmd.get("status", "online"),
                    cmd.get("activity_type"),
                    cmd.get("activity_text"),
                )
                return {"ok": True}
            elif action == "reaction_add":
                return await _action_reaction_add(cmd)
            elif action == "reaction_remove":
                return await _action_reaction_remove(cmd)
            elif action == "stream_start":
                return await _handle_stream_start(cmd)
            elif action == "stream_chunk":
                return await _handle_stream_chunk(cmd)
            elif action == "stream_end":
                return await _handle_stream_end(cmd)
            elif action == "interaction_followup":
                return await _action_interaction_followup(cmd)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    # ── Action Handlers ────────────────────────────────────────────

    async def _action_send(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd["channel_id"])
        if not ch:
            return {"error": f"Channel not found: {cmd['channel_id']}"}
        content = cmd.get("content", "")
        files = []
        for f in cmd.get("files", []):
            files.append(discord.File(f))
        kwargs = {"content": content}
        if files:
            kwargs["files"] = files
        msg = await ch.send(**kwargs)
        return {"ok": True, "message_id": str(msg.id)}

    async def _action_reply(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd["channel_id"])
        if not ch:
            return {"error": f"Channel not found: {cmd['channel_id']}"}
        original = await ch.fetch_message(int(cmd["message_id"]))
        content = cmd.get("content", "")
        files = []
        for f in cmd.get("files", []):
            files.append(discord.File(f))
        kwargs = {"content": content}
        if files:
            kwargs["files"] = files
        msg = await original.reply(**kwargs)
        return {"ok": True, "message_id": str(msg.id)}

    async def _action_edit(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd["channel_id"])
        if not ch:
            return {"error": f"Channel not found: {cmd['channel_id']}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        await msg.edit(content=cmd.get("content", ""))
        return {"ok": True}

    async def _action_delete(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd["channel_id"])
        if not ch:
            return {"error": f"Channel not found: {cmd['channel_id']}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        await msg.delete()
        return {"ok": True}

    async def _action_reaction_add(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd["channel_id"])
        if not ch:
            return {"error": f"Channel not found: {cmd['channel_id']}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        await msg.add_reaction(cmd["emoji"])
        return {"ok": True}

    async def _action_reaction_remove(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd["channel_id"])
        if not ch:
            return {"error": f"Channel not found: {cmd['channel_id']}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        await msg.remove_reaction(cmd["emoji"], client.user)
        return {"ok": True}

    async def _action_interaction_followup(cmd: dict) -> dict:
        itk = cmd.get("interaction_token")
        interaction = interactions.get(itk)
        if not interaction:
            return {"error": f"Unknown interaction: {itk}"}
        content = cmd.get("content", "")
        try:
            await interaction.followup.send(content)
        except discord.HTTPException as e:
            return {"error": f"Followup failed: {e}"}
        interactions.pop(itk, None)
        return {"ok": True}

    # ── Run ─────────────────────────────────────────────────────────

    try:
        asyncio.run(client.start(token))
    except KeyboardInterrupt:
        emit({"event": "shutdown"})
