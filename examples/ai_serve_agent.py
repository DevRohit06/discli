"""
All-in-one AI Discord agent using discli serve + Claude Agent SDK.

Two communication channels:
1. Claude runs discli CLI commands via Bash (messages, embeds, channels, roles, etc.)
2. Agent script sends serve JSONL directly (buttons, selects, modals, streaming, interactions)

Claude tells the agent what components to send via structured JSON in its response.
The agent parses it and sends the right JSONL to serve.

Requirements:
    pip install discord-cli-agent claude-agent-sdk

Usage:
    discli config set token YOUR_BOT_TOKEN
    python examples/ai_serve_agent.py
"""

import asyncio
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

os.environ.pop("CLAUDECODE", None)

import claude_agent_sdk as sdk

# ── Config ──────────────────────────────────────────────────────

SLASH_COMMANDS = [
    {"name": "ask", "description": "Ask the AI anything", "params": [
        {"name": "question", "type": "string", "description": "Your question"}
    ]},
    {"name": "help", "description": "Show what I can do"},
    {"name": "summarize", "description": "Summarize recent conversation", "params": [
        {"name": "messages", "type": "integer", "description": "Number of messages (default: 20)", "required": False}
    ]},
    {"name": "clear", "description": "Clear your conversation history"},
]

SYSTEM_PROMPT = """You are a Discord bot with FULL control over Discord servers.

## How to interact with Discord

Use the Bash tool to run discli CLI commands for messaging, channels, roles, members, etc.

### Messaging
```bash
discli message send CHANNEL_ID "text"
discli message send CHANNEL_ID "text" --embed-title "Title" --embed-desc "Desc" --embed-color 5865F2 --embed-footer "Footer" --embed-field "Name::Value::true"
discli message reply CHANNEL_ID MESSAGE_ID "reply text"
discli message edit CHANNEL_ID MESSAGE_ID "new text"
discli -y message delete CHANNEL_ID MESSAGE_ID
discli message search CHANNEL_ID "query" --limit 50
discli --json message list CHANNEL_ID --limit 10
```

### Embed colors: 5865F2 (blue), ED4245 (red), 57F287 (green), FEE75C (yellow), ff0000, 00ff00

### Channels
```bash
discli channel list --server "Server"
discli channel create "Server" "name" --type text
discli channel edit "#ch" --topic "New topic" --slowmode 5
discli -y channel delete "#ch"
discli channel info "#ch"
discli channel set-permissions "#ch" "Role" --allow send_messages --deny manage_messages
```

### Threads
```bash
discli thread create "#ch" MSG_ID "Thread Name"
discli thread send THREAD_ID "message"
discli thread rename THREAD_ID "New Name"
discli thread archive THREAD_ID
```

### Roles
```bash
discli role list "Server"
discli role create "Server" "Role" --color ff0000
discli role edit "Server" "Role" --name "New" --color 00ff00 --hoist --mentionable
discli role assign "Server" "member" "Role"
discli role remove "Server" "member" "Role"
discli -y role delete "Server" "Role"
```

### Members
```bash
discli member list "Server" --limit 50
discli member info "Server" "member"
discli -y member timeout "Server" "member" SECONDS --reason "reason"
discli -y member timeout "Server" "member" 0  # remove timeout
```

### Reactions
```bash
discli reaction add CHANNEL_ID MSG_ID 👍
discli reaction list CHANNEL_ID MSG_ID
discli reaction users CHANNEL_ID MSG_ID 👍
```

### Polls, Webhooks, Events, DMs, Server
```bash
discli poll create "#ch" "Question?" Opt1 Opt2 --duration 1
discli poll results "#ch" MSG_ID
discli webhook create "#ch" "Name"
discli webhook list "#ch"
discli event create "Server" "Name" "2026-04-01T18:00:00" --location "Place" --end-time "2026-04-01T20:00:00"
discli event list "Server"
discli dm send USER_ID "message"
discli server info "Server"
discli --json server list
```

## INTERACTIVE COMPONENTS (buttons, selects, modals)

The CLI cannot send buttons/selects/modals. Instead, output a special COMPONENT block.
The bot framework will parse this and send it via the serve protocol.

### To send buttons:
```component
{"channel_id": "CHANNEL_ID", "content": "Click a button:", "components": [
  [
    {"type": "button", "label": "Accept", "style": "success", "custom_id": "accept", "emoji": "✅"},
    {"type": "button", "label": "Decline", "style": "danger", "custom_id": "decline", "emoji": "❌"},
    {"type": "button", "label": "Docs", "style": "link", "url": "https://example.com"}
  ]
]}
```

### To send a select menu:
```component
{"channel_id": "CHANNEL_ID", "content": "Pick one:", "components": [
  [{"type": "select", "custom_id": "color_pick", "placeholder": "Choose...", "options": [
    {"label": "Red", "value": "red", "emoji": "🔴"},
    {"label": "Blue", "value": "blue", "emoji": "🔵"}
  ]}]
]}
```

### To send user/role/channel pickers:
```component
{"channel_id": "CHANNEL_ID", "content": "Select a user:", "components": [
  [{"type": "user_select", "custom_id": "pick_user", "placeholder": "Choose someone..."}]
]}
```
Types: user_select, role_select, channel_select

### To send embeds WITH buttons:
```component
{"channel_id": "CHANNEL_ID", "content": "", "embed": {"title": "Vote!", "description": "Pick one", "color": "5865F2"}, "components": [
  [
    {"type": "button", "label": "Option A", "style": "primary", "custom_id": "vote_a"},
    {"type": "button", "label": "Option B", "style": "primary", "custom_id": "vote_b"}
  ]
]}
```

### Button styles: primary (blue), secondary (grey), success (green), danger (red), link (needs "url")
### To disable a button add "disabled": true

### To reply with components (reply to a message):
```component
{"channel_id": "CHANNEL_ID", "message_id": "MSG_ID", "content": "Here you go:", "components": [...]}
```
If message_id is present, it replies. Otherwise it sends a new message.

### To send a button that opens a modal when clicked:
Use a ```modal block to define the modal, then reference it with custom_id "modal:MODAL_ID":
```modal
{"modal_id": "feedback_form", "title": "Feedback", "fields": [
  {"label": "Name", "custom_id": "name", "style": "short", "placeholder": "Your name", "required": true},
  {"label": "Message", "custom_id": "message", "style": "long", "placeholder": "Your feedback"}
]}
```
```component
{"channel_id": "CHANNEL_ID", "content": "Click to open form:", "components": [
  [{"type": "button", "label": "Open Form", "style": "primary", "custom_id": "modal:feedback_form"}]
]}
```
The ```modal block registers the modal. When the button is clicked, the framework opens it automatically.
You can register multiple modals and reference them from different buttons.

## RULES
- Use -y on ALL destructive commands (delete, kick, ban, timeout)
- Use --json when READING data
- IMPORTANT: When sending components, always include "content" with at least a space " " — Discord rejects empty messages
- For components: output a ```component block — the framework handles the rest
- You CAN mix: run discli commands AND output component blocks in the same response
- Always give the user a response — never leave them hanging
- Be concise and friendly
"""

# ── State ───────────────────────────────────────────────────────

conversations: dict[str, list[dict]] = defaultdict(list)
bot_info: dict = {}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr)


# ── Component parser ────────────────────────────────────────────

COMPONENT_BLOCK_RE = re.compile(r"```component\s*\n(.*?)\n```", re.DOTALL)
MODAL_BLOCK_RE = re.compile(r"```modal\s*\n(.*?)\n```", re.DOTALL)

# Store modal definitions: modal_id -> {"title": ..., "fields": [...]}
modal_registry: dict[str, dict] = {}


def extract_blocks(text: str) -> list[dict]:
    """Extract ```component and ```modal blocks from Claude's response."""
    # First, register any modal definitions
    for match in MODAL_BLOCK_RE.finditer(text):
        try:
            data = json.loads(match.group(1).strip())
            mid = data.get("modal_id")
            if mid:
                modal_registry[mid] = data
                log(f"  Registered modal: {mid}")
        except json.JSONDecodeError:
            log(f"  Bad modal JSON: {match.group(1)[:80]}")

    # Then extract component blocks
    components = []
    for match in COMPONENT_BLOCK_RE.finditer(text):
        try:
            data = json.loads(match.group(1).strip())
            components.append(data)
        except json.JSONDecodeError:
            log(f"  Bad component JSON: {match.group(1)[:80]}")
    return components


# ── Main ────────────────────────────────────────────────────────

async def main():
    # Write slash commands
    slash_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(SLASH_COMMANDS, slash_file)
    slash_file.close()

    # Start discli serve
    proc = await asyncio.create_subprocess_exec(
        "discli", "--json", "serve",
        "--slash-commands", slash_file.name,
        "--status", "online",
        "--activity", "listening",
        "--activity-text", "your messages",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    req_counter = 0

    async def serve_send(action: str, **kwargs):
        nonlocal req_counter
        req_counter += 1
        cmd = {"action": action, "req_id": str(req_counter), **kwargs}
        proc.stdin.write((json.dumps(cmd) + "\n").encode())
        await proc.stdin.drain()

    async def send_component(data: dict):
        """Send a component message via serve JSONL."""
        channel_id = data.get("channel_id")
        if not channel_id:
            log("  Component missing channel_id")
            return

        action_data = {"channel_id": channel_id}

        # Discord requires content or embed — never empty
        content = data.get("content", "").strip()
        has_embed = "embed" in data and data["embed"]
        if not content and not has_embed:
            action_data["content"] = "\u200b"  # zero-width space
        elif content:
            action_data["content"] = content

        if has_embed:
            action_data["embed"] = data["embed"]
        if data.get("components"):
            action_data["components"] = data["components"]

        # Reply or send
        if data.get("message_id"):
            await serve_send("reply", message_id=data["message_id"], **action_data)
        else:
            await serve_send("send", **action_data)

        log(f"  Sent component to {channel_id}")

    # ── Claude ──

    options = sdk.ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=10,
    )

    async def ask_claude(claude: sdk.ClaudeSDKClient, prompt: str, user_id: str):
        """Query Claude and process component blocks from response."""
        conversations[user_id].append({"role": "user", "content": prompt})
        conversations[user_id] = conversations[user_id][-20:]

        history = "\n".join(
            f"{'User' if m['role'] == 'user' else 'You'}: {m['content'][:300]}"
            for m in conversations[user_id][-6:]
        )

        full_prompt = f"""Conversation:
{history}

Current: {prompt}"""

        await claude.query(full_prompt)

        full_response = ""
        async for message in claude.receive_response():
            if isinstance(message, sdk.AssistantMessage):
                for block in message.content:
                    if isinstance(block, sdk.TextBlock) and block.text.strip():
                        full_response = block.text.strip()
            elif isinstance(message, sdk.ResultMessage):
                cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
                log(f"  Claude done. Cost: {cost}")

        # Extract and send any component/modal blocks
        components = extract_blocks(full_response)
        for comp in components:
            await send_component(comp)

        if full_response:
            conversations[user_id].append({"role": "assistant", "content": full_response[:500]})

    # ── Event loop ──

    log("Starting AI Serve Agent...")

    async with sdk.ClaudeSDKClient(options) as claude:
        log("Claude session connected.")

        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                data = json.loads(line.decode().strip())
                event = data.get("event")

                # ── Ready ──
                if event == "ready":
                    bot_info.update(data)
                    log(f"Bot connected as {data['bot_name']}")

                elif event == "response":
                    if data.get("error"):
                        log(f"  Serve error: {data['error']}")

                elif event == "slash_commands_synced":
                    log(f"Synced {data['count']} slash commands to {data['guilds']} guilds")

                # ── Messages ──
                elif event == "message":
                    if data.get("is_bot"):
                        continue
                    if not data.get("mentions_bot") and not data.get("is_dm"):
                        continue

                    user_id = data["author_id"]
                    user_name = data["author"]
                    content = data["content"]
                    channel_id = data["channel_id"]
                    message_id = data["message_id"]
                    server_name = data.get("server", "")
                    guild_id = data.get("server_id", "")

                    log(f"[{user_name}] {content[:100]}")
                    await serve_send("typing_start", channel_id=channel_id)

                    prompt = f"""User "{user_name}" (ID: {user_id}) says: {content}

Channel ID: {channel_id}
Message ID: {message_id}
Server: "{server_name}" (ID: {guild_id})

Respond using discli commands. For components (buttons/selects/modals), use ```component blocks.
Always make sure the user gets a visible response."""

                    await ask_claude(claude, prompt, user_id)
                    await serve_send("typing_stop", channel_id=channel_id)

                # ── Slash commands ──
                elif event == "slash_command":
                    command = data["command"]
                    args = data.get("args", {})
                    user_id = data["user_id"]
                    user_name = data["user"]
                    channel_id = str(data["channel_id"])
                    guild_id = str(data.get("guild_id", ""))
                    itk = data["interaction_token"]

                    log(f"/{command} from {user_name}: {args}")

                    if command == "clear":
                        conversations.pop(user_id, None)
                        await serve_send("interaction_followup",
                                         interaction_token=itk,
                                         content="✅ History cleared!", ephemeral=True)
                        continue

                    if command == "help":
                        await serve_send("interaction_followup",
                            interaction_token=itk, content="",
                            embed={
                                "title": "What I Can Do",
                                "color": "5865F2",
                                "description": "I'm an AI assistant with full Discord control.",
                                "fields": [
                                    {"name": "💬 Chat", "value": "@mention me with anything", "inline": False},
                                    {"name": "🔘 Components", "value": "Buttons, selects, modals", "inline": True},
                                    {"name": "🎨 Embeds", "value": "Rich formatted messages", "inline": True},
                                    {"name": "🛠️ Manage", "value": "Channels, roles, threads, members", "inline": True},
                                    {"name": "📊 Polls", "value": "Create and manage polls", "inline": True},
                                    {"name": "🔗 Webhooks", "value": "Create, list, delete", "inline": True},
                                    {"name": "📅 Events", "value": "Schedule server events", "inline": True},
                                ],
                                "footer": "Powered by discli + Claude",
                            })
                        continue

                    # /ask and /summarize — let Claude handle
                    question = args.get("question") or args.get("messages") or command
                    prompt = f"""Slash command /{command} from "{user_name}" (ID: {user_id}).
Args: {json.dumps(args)}
Channel ID: {channel_id}, Server ID: {guild_id}

Reply using: discli message send {channel_id} "response"
For /summarize: first run discli --json message list {channel_id} --limit {args.get('messages', 20)}"""

                    await ask_claude(claude, prompt, user_id)

                # ── Component interactions ──
                elif event == "component_interaction":
                    cid = data.get("custom_id", "")
                    itk = data["interaction_token"]
                    values = data.get("values", [])
                    user = data["user"]
                    user_id = data["user_id"]
                    channel_id = str(data["channel_id"])
                    guild_id = str(data.get("guild_id", ""))
                    message_id = data.get("message_id", "")

                    log(f"Component: {cid} by {user}, values={values}")

                    # Handle modal buttons — custom_id starts with "modal:"
                    if cid.startswith("modal:"):
                        modal_id = cid[6:]
                        modal_def = modal_registry.get(modal_id)
                        if modal_def:
                            await serve_send("modal_send",
                                             interaction_token=itk,
                                             title=modal_def.get("title", "Form"),
                                             custom_id=modal_def.get("custom_id", modal_id),
                                             fields=modal_def.get("fields", []))
                            log(f"  Opened modal: {modal_def.get('title')}")
                        else:
                            log(f"  Modal not found: {modal_id}")
                            await serve_send("interaction_respond",
                                             interaction_token=itk,
                                             content="Form not found.", ephemeral=True)
                        continue

                    # For other components, acknowledge and let Claude handle
                    await serve_send("interaction_respond",
                                     interaction_token=itk,
                                     content="Processing...", ephemeral=True)

                    prompt = f"""User "{user}" clicked a component.
Custom ID: {cid}
Values: {json.dumps(values)}
Channel ID: {channel_id}, Message ID: {message_id}, Server ID: {guild_id}

Respond appropriately. Use discli message send {channel_id} "response" for text.
Use ```component blocks if you want to send new buttons/selects."""

                    await ask_claude(claude, prompt, user_id)

                # ── Modal submissions ──
                elif event == "modal_submit":
                    itk = data["interaction_token"]
                    fields = data.get("fields", {})
                    user = data["user"]
                    user_id = data["user_id"]
                    channel_id = str(data["channel_id"])

                    log(f"Modal from {user}: {fields}")

                    # Acknowledge
                    await serve_send("interaction_followup",
                                     interaction_token=itk,
                                     content="Got it!", ephemeral=True)

                    field_flags = " ".join(
                        f'--embed-field "{k}::{v}::false"' for k, v in fields.items()
                    )
                    prompt = f"""User "{user}" submitted a form (ID: {data.get('custom_id', '')}).
Fields: {json.dumps(fields, indent=2)}
Channel ID: {channel_id}

Show the submission nicely:
discli message send {channel_id} "" --embed-title "Form Received" --embed-color 57F287 {field_flags}"""

                    await ask_claude(claude, prompt, user_id)

                # ── Voice / Members / Connection ──
                elif event == "voice_state":
                    log(f"Voice: {data.get('member')} {data.get('action')} {data.get('channel', '')}")
                elif event == "member_join":
                    log(f"Joined: {data.get('member')}")
                elif event == "member_remove":
                    log(f"Left: {data.get('member')}")
                elif event == "disconnected":
                    log("⚠ Disconnected")
                elif event == "resumed":
                    log("✓ Reconnected")
                elif event == "error":
                    log(f"ERROR: {data.get('message')}")

        except KeyboardInterrupt:
            log("Shutting down...")
        finally:
            proc.terminate()
            Path(slash_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
