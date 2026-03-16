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
            try:
                await _register_slash_commands()
            except Exception as e:
                emit({"event": "error", "message": f"Slash command registration failed: {e}"})

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
        import inspect

        _type_map = {"string": str, "integer": int, "number": float, "boolean": bool}

        def _make_slash_callback(param_defs):
            """Create a callback whose __signature__ exposes params to discord.py."""
            async def _callback(interaction: discord.Interaction, **kwargs):
                cmd_name = interaction.command.name
                itk = str(uuid.uuid4())
                interactions[itk] = interaction
                await interaction.response.defer(thinking=True)
                # Use interaction.permissions (resolved from Discord payload)
                # rather than guild_permissions (requires member cache)
                perms = interaction.permissions
                is_admin = perms.administrator
                member_permissions = perms.value
                emit({
                    "event": "slash_command",
                    "command": cmd_name,
                    "args": {k: str(v) for k, v in kwargs.items() if v is not None},
                    "channel_id": str(interaction.channel_id),
                    "user": str(interaction.user),
                    "user_id": str(interaction.user.id),
                    "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
                    "interaction_token": itk,
                    "is_admin": is_admin,
                    "member_permissions": member_permissions,
                })

            # Build a proper signature so discord.py registers slash options
            sig_params = [
                inspect.Parameter("interaction", inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                  annotation=discord.Interaction),
            ]
            for p in param_defs:
                annotation = _type_map.get(p.get("type", "string"), str)
                required = p.get("required", True)
                default = inspect.Parameter.empty if required else None
                sig_params.append(
                    inspect.Parameter(p["name"], inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                      annotation=annotation, default=default),
                )
            _callback.__signature__ = inspect.Signature(sig_params)
            return _callback

        for cmd_def in slash_defs:
            name = cmd_def["name"]
            desc = cmd_def.get("description", name)
            params = cmd_def.get("params", [])

            callback = _make_slash_callback(params)
            if params:
                descriptions = {p["name"]: p.get("description", p["name"]) for p in params}
                callback = app_commands.describe(**descriptions)(callback)
            tree.command(name=name, description=desc)(callback)

        # Copy global commands to each guild for instant availability, then sync
        synced_guilds = 0
        for guild in client.guilds:
            try:
                tree.copy_global_to(guild=guild)
                await tree.sync(guild=guild)
                synced_guilds += 1
            except Exception as e:
                emit({"event": "error", "message": f"Failed to sync commands to {guild.name}: {e}"})
        emit({"event": "slash_commands_synced", "count": len(slash_defs), "guilds": synced_guilds})

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
        """Read JSONL commands from stdin and dispatch.

        Uses a thread for reading because asyncio.connect_read_pipe
        fails on Windows (ProactorEventLoop) when stdin is a pipe
        from a parent process (WinError 6: handle is invalid).
        """
        import threading
        from queue import Queue, Empty

        q: Queue[str | None] = Queue()

        def _read_thread():
            try:
                for raw in sys.stdin:
                    q.put(raw.strip())
            except (OSError, ValueError):
                pass
            q.put(None)  # sentinel

        t = threading.Thread(target=_read_thread, daemon=True)
        t.start()

        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, q.get)
                if line is None:
                    await client.close()
                    return
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

    async def _action_typing_start(cmd: dict) -> dict:
        _start_typing(cmd["channel_id"])
        return {"ok": True}

    async def _action_typing_stop(cmd: dict) -> dict:
        _stop_typing(cmd["channel_id"])
        return {"ok": True}

    async def _action_presence_set(cmd: dict) -> dict:
        await _set_presence(
            cmd.get("status", "online"),
            cmd.get("activity_type"),
            cmd.get("activity_text"),
        )
        return {"ok": True}

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

    async def _action_thread_create(cmd: dict) -> dict:
        channel_id = cmd.get("channel_id")
        name = cmd.get("name")
        if not name:
            return {"error": "Missing 'name' for thread"}
        message_id = cmd.get("message_id")
        auto_archive = cmd.get("auto_archive_duration", 1440)
        content = cmd.get("content")

        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return {"error": f"Channel not found: {channel_id}"}

        if message_id:
            msg = await ch.fetch_message(int(message_id))
            thread = await msg.create_thread(name=name, auto_archive_duration=auto_archive)
        else:
            thread = await ch.create_thread(
                name=name,
                auto_archive_duration=auto_archive,
                type=discord.ChannelType.public_thread,
            )

        # Optionally send an initial message in the thread
        if content:
            await thread.send(content)

        return {
            "ok": True,
            "thread_id": str(thread.id),
            "thread_name": thread.name,
        }

    async def _action_thread_send(cmd: dict) -> dict:
        thread_id = cmd.get("thread_id")
        if not thread_id:
            return {"error": "Missing 'thread_id'"}
        content = cmd.get("content", "")
        thread = client.get_channel(int(thread_id))
        if not thread:
            return {"error": f"Thread not found: {thread_id}"}
        files = []
        for f in cmd.get("files", []):
            files.append(discord.File(f))
        kwargs = {"content": content}
        if files:
            kwargs["files"] = files
        msg = await thread.send(**kwargs)
        return {"ok": True, "message_id": str(msg.id)}

    async def _action_poll_send(cmd: dict) -> dict:
        import datetime

        channel_id = cmd.get("channel_id")
        question = cmd.get("question")
        answers = cmd.get("answers", [])
        duration_hours = cmd.get("duration_hours", 24)
        multiple = cmd.get("multiple", False)
        content = cmd.get("content")

        if not question:
            return {"error": "Missing 'question' for poll"}
        if len(answers) < 2:
            return {"error": "Poll needs at least 2 answers"}

        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return {"error": f"Channel not found: {channel_id}"}

        poll = discord.Poll(
            question=question,
            duration=datetime.timedelta(hours=duration_hours),
            multiple=multiple,
        )
        for answer in answers:
            if isinstance(answer, dict):
                poll.add_answer(text=answer["text"], emoji=answer.get("emoji"))
            else:
                poll.add_answer(text=str(answer))

        kwargs = {"poll": poll}
        if content:
            kwargs["content"] = content
        msg = await ch.send(**kwargs)
        return {"ok": True, "message_id": str(msg.id)}

    # ── Message Queries ────────────────────────────────────────────

    async def _action_message_list(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        limit = cmd.get("limit", 20)
        messages = []
        async for msg in ch.history(limit=limit):
            messages.append({
                "id": str(msg.id),
                "author": str(msg.author),
                "author_id": str(msg.author.id),
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "attachments": [
                    {"filename": a.filename, "url": a.url}
                    for a in msg.attachments
                ],
            })
        return {"ok": True, "messages": messages}

    async def _action_message_get(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        return {
            "ok": True,
            "id": str(msg.id),
            "author": str(msg.author),
            "author_id": str(msg.author.id),
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
            "attachments": [
                {"filename": a.filename, "url": a.url}
                for a in msg.attachments
            ],
            "embeds": [
                {"title": e.title, "description": e.description}
                for e in msg.embeds
            ],
            "reply_to": str(msg.reference.message_id)
            if msg.reference
            else None,
        }

    async def _action_message_search(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        query = cmd.get("query", "").lower()
        limit = cmd.get("limit", 100)
        author_filter = cmd.get("author")
        results = []
        async for msg in ch.history(limit=limit):
            if query and query not in msg.content.lower():
                continue
            if author_filter and str(msg.author).lower() != author_filter.lower():
                continue
            results.append({
                "id": str(msg.id),
                "author": str(msg.author),
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
            })
        return {"ok": True, "messages": results}

    async def _action_message_pin(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        await msg.pin()
        return {"ok": True}

    async def _action_message_unpin(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        msg = await ch.fetch_message(int(cmd["message_id"]))
        await msg.unpin()
        return {"ok": True}

    # ── Channel & Server Management ────────────────────────────────

    async def _action_channel_list(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        guilds = (
            [client.get_guild(int(guild_id))] if guild_id else client.guilds
        )
        channels = []
        for guild in guilds:
            if not guild:
                continue
            for ch in guild.channels:
                if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                    channels.append({
                        "id": str(ch.id),
                        "name": ch.name,
                        "type": "text"
                        if isinstance(ch, discord.TextChannel)
                        else "voice",
                        "server": guild.name,
                        "server_id": str(guild.id),
                    })
        return {"ok": True, "channels": channels}

    async def _action_channel_create(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        if not guild_id:
            return {"error": "Missing 'guild_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        name = cmd.get("name")
        if not name:
            return {"error": "Missing 'name'"}
        ch_type = cmd.get("type", "text")
        if ch_type == "voice":
            ch = await guild.create_voice_channel(name)
        elif ch_type == "category":
            ch = await guild.create_category(name)
        else:
            ch = await guild.create_text_channel(name)
        return {"ok": True, "channel_id": str(ch.id), "name": ch.name}

    async def _action_channel_info(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        return {
            "ok": True,
            "id": str(ch.id),
            "name": ch.name,
            "type": str(ch.type),
            "server": ch.guild.name if ch.guild else None,
            "server_id": str(ch.guild.id) if ch.guild else None,
            "topic": getattr(ch, "topic", None),
            "created_at": ch.created_at.isoformat(),
        }

    def _action_server_list(cmd: dict) -> dict:
        servers = []
        for guild in client.guilds:
            servers.append({
                "id": str(guild.id),
                "name": guild.name,
                "member_count": guild.member_count,
            })
        return {"ok": True, "servers": servers}

    async def _action_server_info(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        if not guild_id:
            return {"error": "Missing 'guild_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        return {
            "ok": True,
            "id": str(guild.id),
            "name": guild.name,
            "owner": str(guild.owner) if guild.owner else None,
            "member_count": guild.member_count,
            "channel_count": len(guild.channels),
            "role_count": len(guild.roles),
            "created_at": guild.created_at.isoformat(),
        }

    # ── DM ─────────────────────────────────────────────────────────

    async def _action_dm_send(cmd: dict) -> dict:
        user_id = cmd.get("user_id")
        if not user_id:
            return {"error": "Missing 'user_id'"}
        user = client.get_user(int(user_id))
        if not user:
            try:
                user = await client.fetch_user(int(user_id))
            except discord.NotFound:
                return {"error": f"User not found: {user_id}"}
        dm = await user.create_dm()
        content = cmd.get("content", "")
        msg = await dm.send(content=content)
        return {
            "ok": True,
            "message_id": str(msg.id),
            "recipient": str(user),
        }

    # ── Members & Roles ────────────────────────────────────────────

    async def _action_member_list(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        if not guild_id:
            return {"error": "Missing 'guild_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        limit = cmd.get("limit", 50)
        members = []
        for m in guild.members[:limit]:
            members.append({
                "id": str(m.id),
                "name": str(m),
                "nick": m.nick,
                "bot": m.bot,
            })
        return {"ok": True, "members": members}

    async def _action_member_info(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        member_id = cmd.get("member_id")
        if not guild_id or not member_id:
            return {"error": "Missing 'guild_id' or 'member_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        member = guild.get_member(int(member_id))
        if not member:
            return {"error": f"Member not found: {member_id}"}
        return {
            "ok": True,
            "id": str(member.id),
            "name": str(member),
            "nick": member.nick,
            "bot": member.bot,
            "roles": [
                {"id": str(r.id), "name": r.name}
                for r in member.roles
                if r.name != "@everyone"
            ],
            "joined_at": member.joined_at.isoformat()
            if member.joined_at
            else None,
        }

    async def _action_role_list(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        if not guild_id:
            return {"error": "Missing 'guild_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        roles = []
        for r in guild.roles:
            if r.name == "@everyone":
                continue
            roles.append({
                "id": str(r.id),
                "name": r.name,
                "color": str(r.color),
                "members": len(r.members),
            })
        return {"ok": True, "roles": roles}

    async def _action_role_assign(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        member_id = cmd.get("member_id")
        role_id = cmd.get("role_id")
        if not all([guild_id, member_id, role_id]):
            return {"error": "Missing 'guild_id', 'member_id', or 'role_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        member = guild.get_member(int(member_id))
        if not member:
            return {"error": f"Member not found: {member_id}"}
        role = guild.get_role(int(role_id))
        if not role:
            return {"error": f"Role not found: {role_id}"}
        await member.add_roles(role)
        return {"ok": True, "member": str(member), "role": role.name}

    async def _action_role_remove(cmd: dict) -> dict:
        guild_id = cmd.get("guild_id")
        member_id = cmd.get("member_id")
        role_id = cmd.get("role_id")
        if not all([guild_id, member_id, role_id]):
            return {"error": "Missing 'guild_id', 'member_id', or 'role_id'"}
        guild = client.get_guild(int(guild_id))
        if not guild:
            return {"error": f"Server not found: {guild_id}"}
        member = guild.get_member(int(member_id))
        if not member:
            return {"error": f"Member not found: {member_id}"}
        role = guild.get_role(int(role_id))
        if not role:
            return {"error": f"Role not found: {role_id}"}
        await member.remove_roles(role)
        return {"ok": True, "member": str(member), "role": role.name}

    # ── Thread Queries ─────────────────────────────────────────────

    async def _action_thread_list(cmd: dict) -> dict:
        ch = resolve_channel_by_id(cmd.get("channel_id"))
        if not ch:
            return {"error": f"Channel not found: {cmd.get('channel_id')}"}
        threads = []
        for t in ch.threads:
            threads.append({
                "id": str(t.id),
                "name": t.name,
                "message_count": t.message_count,
                "member_count": t.member_count,
                "archived": t.archived,
            })
        return {"ok": True, "threads": threads}

    # ── Action Dispatch ────────────────────────────────────────────

    _actions: dict[str, callable] = {
        # Messaging
        "send": _action_send,
        "reply": _action_reply,
        "edit": _action_edit,
        "delete": _action_delete,
        "message_list": _action_message_list,
        "message_get": _action_message_get,
        "message_search": _action_message_search,
        "message_pin": _action_message_pin,
        "message_unpin": _action_message_unpin,
        # Streaming
        "stream_start": _handle_stream_start,
        "stream_chunk": _handle_stream_chunk,
        "stream_end": _handle_stream_end,
        # Interactions
        "interaction_followup": _action_interaction_followup,
        # Typing & presence
        "typing_start": _action_typing_start,
        "typing_stop": _action_typing_stop,
        "presence": _action_presence_set,
        # Reactions
        "reaction_add": _action_reaction_add,
        "reaction_remove": _action_reaction_remove,
        # Threads
        "thread_create": _action_thread_create,
        "thread_send": _action_thread_send,
        "thread_list": _action_thread_list,
        # Polls
        "poll_send": _action_poll_send,
        # Channels
        "channel_list": _action_channel_list,
        "channel_create": _action_channel_create,
        "channel_info": _action_channel_info,
        # DMs
        "dm_send": _action_dm_send,
        # Members & roles
        "member_list": _action_member_list,
        "member_info": _action_member_info,
        "role_list": _action_role_list,
        "role_assign": _action_role_assign,
        "role_remove": _action_role_remove,
        # Server
        "server_list": _action_server_list,
        "server_info": _action_server_info,
    }

    async def _dispatch(cmd: dict) -> dict:
        action = cmd.get("action")
        if not action:
            return {"error": "Missing 'action' field"}

        handler = _actions.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}

        try:
            result = handler(cmd)
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            return {"error": str(e)}

    # ── Run ─────────────────────────────────────────────────────────

    try:
        asyncio.run(client.start(token))
    except KeyboardInterrupt:
        emit({"event": "shutdown"})
