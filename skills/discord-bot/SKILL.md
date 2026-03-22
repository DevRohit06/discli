---
name: discord-bot
description: "Build Discord bots with discli. Scaffolds a complete bot using discli serve mode with JSONL protocol — handles events, slash commands, streaming responses, embeds, components, and more. Works with Python or Bash."
---

# Discord Bot Builder

Build Discord bots using `discli serve` — the bidirectional JSONL protocol for persistent Discord bots.

## When to Use

Use this skill when the user wants to:
- Build a Discord bot from scratch
- Create a bot that responds to messages, slash commands, or reactions
- Build a bot with buttons, embeds, or interactive components
- Scaffold a serve-mode bot script

## Prerequisites

```bash
pip install discord-cli-agent
discli config set token YOUR_BOT_TOKEN
```

## Architecture

All bots follow this pattern:

```
Python script
  └─ subprocess: discli serve [--slash-commands cmds.json]
       ├─ stdout → JSONL events (message, slash_command, reaction_add, ...)
       └─ stdin  ← JSONL commands (send, reply, stream_start, ...)
```

## Bot Template (Python, async)

```python
import asyncio
import json
import tempfile
from pathlib import Path

SLASH_COMMANDS = [
    # Define slash commands here
    # {"name": "help", "description": "Show help", "params": []},
]


async def main():
    # Write slash commands to temp file
    slash_file = None
    serve_args = ["discli", "--json", "serve", "--status", "online"]
    if SLASH_COMMANDS:
        slash_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(SLASH_COMMANDS, slash_file)
        slash_file.close()
        serve_args += ["--slash-commands", slash_file.name]

    proc = await asyncio.create_subprocess_exec(
        *serve_args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    req_counter = 0

    async def send(action: str, **kwargs) -> None:
        nonlocal req_counter
        req_counter += 1
        cmd = {"action": action, "req_id": str(req_counter), **kwargs}
        proc.stdin.write((json.dumps(cmd) + "\n").encode())
        await proc.stdin.drain()

    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            event = json.loads(line.decode().strip())
            await handle_event(event, send)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        if slash_file:
            Path(slash_file.name).unlink(missing_ok=True)


async def handle_event(event: dict, send) -> None:
    """Route events to handlers."""
    etype = event.get("event")

    if etype == "ready":
        print(f"Connected as {event['bot_name']}")

    elif etype == "message":
        if event.get("is_bot"):
            return
        await on_message(event, send)

    elif etype == "slash_command":
        await on_slash_command(event, send)

    elif etype == "component_interaction":
        await on_component(event, send)

    elif etype == "reaction_add":
        await on_reaction(event, send)


async def on_message(event: dict, send) -> None:
    """Handle incoming messages. Customize this."""
    if event.get("mentions_bot"):
        await send("typing_start", channel_id=event["channel_id"])
        # ... your logic here ...
        await send("typing_stop", channel_id=event["channel_id"])
        await send("reply",
                    channel_id=event["channel_id"],
                    message_id=event["message_id"],
                    content="Hello!")


async def on_slash_command(event: dict, send) -> None:
    """Handle slash commands. Customize this."""
    await send("interaction_followup",
               interaction_token=event["interaction_token"],
               content=f"Received /{event['command']}")


async def on_component(event: dict, send) -> None:
    """Handle button clicks and select menus."""
    pass


async def on_reaction(event: dict, send) -> None:
    """Handle reaction adds."""
    pass


if __name__ == "__main__":
    asyncio.run(main())
```

## Serve Mode JSONL Reference

### Events (stdout — from Discord)

| Event | Key Fields |
|-------|-----------|
| `ready` | `bot_id`, `bot_name` |
| `message` | `channel_id`, `message_id`, `author`, `author_id`, `content`, `mentions_bot`, `is_dm`, `attachments`, `reply_to` |
| `message_edit` | `channel_id`, `message_id`, `old_content`, `new_content` |
| `message_delete` | `channel_id`, `message_id`, `content` |
| `slash_command` | `command`, `args`, `channel_id`, `user`, `user_id`, `interaction_token`, `is_admin` |
| `reaction_add` | `channel_id`, `message_id`, `emoji`, `user`, `user_id` |
| `reaction_remove` | same as above |
| `member_join` | `server`, `member`, `member_id` |
| `member_remove` | same as above |
| `voice_state` | `action` (joined/left/moved/updated), `member`, `channel`, `channel_id` |
| `component_interaction` | `custom_id`, `values`, `channel_id`, `message_id`, `user`, `interaction_token` |
| `modal_submit` | `custom_id`, `fields`, `channel_id`, `user`, `interaction_token` |
| `disconnected` | (no fields) |
| `resumed` | (no fields) |

### Actions (stdin — to Discord)

**Messaging:**
```json
{"action": "send", "channel_id": "ID", "content": "text"}
{"action": "send", "channel_id": "ID", "content": "text", "embed": {"title": "T", "description": "D", "color": "ff0000", "fields": [{"name": "N", "value": "V", "inline": true}], "footer": "F", "image": "URL", "thumbnail": "URL"}}
{"action": "send", "channel_id": "ID", "content": "text", "components": [[{"type": "button", "label": "Click", "style": "primary", "custom_id": "btn1"}]]}
{"action": "reply", "channel_id": "ID", "message_id": "ID", "content": "text"}
{"action": "edit", "channel_id": "ID", "message_id": "ID", "content": "new text"}
{"action": "delete", "channel_id": "ID", "message_id": "ID"}
{"action": "message_bulk_delete", "channel_id": "ID", "message_ids": ["1", "2", "3"]}
```

**Streaming (for token-by-token AI responses):**
```json
{"action": "stream_start", "channel_id": "ID", "reply_to": "MSG_ID"}
{"action": "stream_chunk", "stream_id": "SID", "content": "tokens..."}
{"action": "stream_end", "stream_id": "SID"}
```

**Interactions:**
```json
{"action": "interaction_followup", "interaction_token": "ITK", "content": "response"}
{"action": "modal_send", "interaction_token": "ITK", "title": "Form", "custom_id": "form1", "fields": [{"label": "Name", "custom_id": "name", "style": "short"}]}
```

**Typing & Presence:**
```json
{"action": "typing_start", "channel_id": "ID"}
{"action": "typing_stop", "channel_id": "ID"}
{"action": "presence", "status": "online", "activity_type": "playing", "activity_text": "text"}
```

**Threads:**
```json
{"action": "thread_create", "channel_id": "ID", "name": "Thread", "content": "First message"}
{"action": "thread_send", "thread_id": "ID", "content": "text"}
{"action": "thread_archive", "thread_id": "ID", "archived": true}
{"action": "thread_rename", "thread_id": "ID", "name": "New Name"}
```

**Channels:**
```json
{"action": "channel_list", "guild_id": "ID"}
{"action": "channel_create", "guild_id": "ID", "name": "new-ch", "type": "text"}
{"action": "channel_edit", "channel_id": "ID", "topic": "New topic", "slowmode": 10}
{"action": "forum_post", "channel_id": "ID", "title": "Post", "content": "Body"}
```

**Members, Roles, Webhooks, Events:**
```json
{"action": "member_list", "guild_id": "ID", "limit": 50}
{"action": "member_timeout", "guild_id": "ID", "member_id": "ID", "duration": 3600}
{"action": "role_edit", "guild_id": "ID", "role_id": "ID", "name": "New Name", "color": "ff0000"}
{"action": "webhook_create", "channel_id": "ID", "name": "My Hook"}
{"action": "event_create", "guild_id": "ID", "name": "Hangout", "start_time": "ISO", "location": "Park", "end_time": "ISO"}
```

## Slash Command JSON Format

```json
[
  {"name": "help", "description": "Show help"},
  {"name": "ask", "description": "Ask the bot", "params": [
    {"name": "question", "type": "string", "description": "Your question", "required": true}
  ]},
  {"name": "config", "description": "Configure settings", "params": [
    {"name": "key", "type": "string", "description": "Setting name"},
    {"name": "value", "type": "string", "description": "Setting value", "required": false}
  ]}
]
```

Param types: `string`, `integer`, `number`, `boolean`

## Button Styles

| Style | Use for |
|-------|---------|
| `primary` | Main action (blue) |
| `secondary` | Alternative (grey) |
| `success` | Confirm (green) |
| `danger` | Destructive (red) |
| `link` | External URL (requires `url` instead of `custom_id`) |

## Guidelines

- Always check `is_bot` to skip bot messages and avoid loops
- Use `mentions_bot` to respond only when addressed
- Use `typing_start`/`typing_stop` to show the bot is "thinking"
- Use streaming for long AI responses — users see text appear progressively
- Track `req_id` in commands and `response` events for async correlation
- Keep embed descriptions under 4096 chars, field values under 1024
- Discord messages max 2000 chars — use streaming for longer content (auto-splits)
- Store the `interaction_token` from `slash_command` events to respond later
- Slash command responses must happen within 15 minutes of the interaction
