"""
AI Discord agent powered by Claude via the Claude Agent SDK — with voice
(TTS/STT), interactive components (buttons, selects, modals), and everything
else discli exposes.

Uses `discli serve` for bidirectional communication over stdin/stdout JSONL.
Claude runs discli CLI commands via the Bash tool for actions; the agent
script forwards events and parses ```component / ```modal blocks from
Claude's responses to send richer interactions back.

Uses your existing Claude Code authentication — no API key needed.
Keeps a single persistent Claude Code session for all events.
Loads agent instructions from agents/discord-agent.md.

Requirements:
    pip install "discord-cli-agent[voice]" claude-agent-sdk
    # Optional voice providers:
    pip install "discord-cli-agent[elevenlabs,deepgram]"

Usage:
    discli config set token YOUR_BOT_TOKEN
    python examples/claude_agent.py
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

# Allow running inside a Claude Code session
os.environ.pop("CLAUDECODE", None)

# Force UTF-8 stdout/stderr on Windows so emoji / non-ASCII prints don't crash
# with UnicodeEncodeError under the default cp1252 codec.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import claude_agent_sdk as sdk

# Load canonical agent instructions (covers messages, voice, interactive, etc.)
INSTRUCTIONS_PATH = Path(__file__).parent.parent / "agents" / "discord-agent.md"
AGENT_INSTRUCTIONS = INSTRUCTIONS_PATH.read_text(encoding="utf-8")

# Voice provider config — override via env vars.
# STT: "deepgram" | "openai"   TTS: "openai" | "elevenlabs" | "deepgram"
STT_PROVIDER = os.environ.get("DISCLI_STT", "deepgram")
TTS_PROVIDER = os.environ.get("DISCLI_TTS", "openai")
# Each TTS provider uses different voice identifiers; pick a safe default per
# provider unless the user overrides via DISCLI_TTS_VOICE.
_DEFAULT_TTS_VOICES = {
    "openai": "alloy",
    "elevenlabs": "Rachel",
    "deepgram": "aura-2-asteria-en",
}
TTS_VOICE = os.environ.get("DISCLI_TTS_VOICE") or _DEFAULT_TTS_VOICES.get(
    TTS_PROVIDER, "default"
)

SYSTEM_PROMPT = f"""{AGENT_INSTRUCTIONS}

## Your Persona

You are a helpful, concise, and friendly Discord agent with full control over
messages, voice channels, and interactive components (buttons, selects, modals).
If you don't know something, say so.

## How you respond

**Text:** always reply to the specific triggering message with
`discli message reply <channel> <message_id> "..."`.

**Voice:** the CLI `discli voice` commands are ONE-SHOT — each call spins up a
fresh Discord client that joins and disconnects when the command exits. For
**persistent** voice (the bot stays in the channel and can listen + speak),
you must emit ```voice blocks instead. The framework routes them through the
already-connected serve bot.

Supported voice actions (each block is valid JSON, one action per block):
```voice
{{"action": "connect", "channel_id": "VOICE_CHANNEL_ID"}}
```
```voice
{{"action": "speak", "channel_id": "VOICE_CHANNEL_ID", "text": "Hello there!", "tts": "{TTS_PROVIDER}", "voice": "{TTS_VOICE}"}}
```
```voice
{{"action": "listen_start", "channel_id": "VOICE_CHANNEL_ID", "stt": "{STT_PROVIDER}", "duration": 120}}
```
```voice
{{"action": "listen_stop", "channel_id": "VOICE_CHANNEL_ID"}}
```
```voice
{{"action": "disconnect", "channel_id": "VOICE_CHANNEL_ID"}}
```

Other actions: `play` (with `audio_url`), `stop`, `pause`, `resume`, `status`,
`set_config` (set `tts`/`stt`/`vad_enabled`).

When someone asks you to join voice: emit a `connect` block, then immediately
a `listen_start` block (using stt="{STT_PROVIDER}") so you can hear them. When
a `voice_speech_detected` event fires, emit a `speak` block (using
tts="{TTS_PROVIDER}", voice="{TTS_VOICE}") to reply. Keep voice replies short
(1–2 sentences, conversational).

Voice requires: `pip install "discord-cli-agent[voice]"` plus a TTS/STT
provider (e.g. `[openai-voice]`, `[elevenlabs]`, `[deepgram]`) and FFmpeg on
PATH. Missing deps surface as errors in the `response` event.

**Interactive components:** to send buttons, selects, user/role/channel pickers,
or modals you CANNOT use the CLI — the framework parses special fenced blocks
from your response and sends them via the serve protocol.

Send a component block like this (valid JSON inside the fence):
```component
{{"channel_id": "CHANNEL_ID", "content": "Click one:", "components": [
  [
    {{"type": "button", "label": "Yes", "style": "success", "custom_id": "yes"}},
    {{"type": "button", "label": "No", "style": "danger", "custom_id": "no"}}
  ]
]}}
```

Register a modal and a button that opens it:
```modal
{{"modal_id": "feedback", "title": "Feedback", "fields": [
  {{"label": "Message", "custom_id": "msg", "style": "long", "required": true}}
]}}
```
```component
{{"channel_id": "CHANNEL_ID", "content": "Share feedback:", "components": [
  [{{"type": "button", "label": "Open form", "style": "primary", "custom_id": "modal:feedback"}}]
]}}
```

Rules:
- Components must include non-empty `content` (Discord rejects empty messages —
  the framework inserts a zero-width space for you if you omit it).
- You MAY mix: run discli commands AND output ```component / ```modal blocks.
- Always reply — never leave the user hanging.
"""


# ── Component / modal block parsing ─────────────────────────────────────────

COMPONENT_BLOCK_RE = re.compile(r"```component\s*\n(.*?)\n```", re.DOTALL)
MODAL_BLOCK_RE = re.compile(r"```modal\s*\n(.*?)\n```", re.DOTALL)
VOICE_BLOCK_RE = re.compile(r"```voice\s*\n(.*?)\n```", re.DOTALL)

modal_registry: dict[str, dict] = {}


def extract_blocks(text: str) -> tuple[list[dict], list[dict]]:
    """Pull ```component / ```modal / ```voice JSON blocks from Claude's response.

    Returns (components, voice_actions). Modals are registered as a side effect.
    """
    for match in MODAL_BLOCK_RE.finditer(text):
        try:
            data = json.loads(match.group(1).strip())
            mid = data.get("modal_id")
            if mid:
                modal_registry[mid] = data
                print(f"  Registered modal: {mid}")
        except json.JSONDecodeError:
            print(f"  Bad modal JSON: {match.group(1)[:80]}")

    components = []
    for match in COMPONENT_BLOCK_RE.finditer(text):
        try:
            components.append(json.loads(match.group(1).strip()))
        except json.JSONDecodeError:
            print(f"  Bad component JSON: {match.group(1)[:80]}")

    voice_actions = []
    for match in VOICE_BLOCK_RE.finditer(text):
        try:
            voice_actions.append(json.loads(match.group(1).strip()))
        except json.JSONDecodeError:
            print(f"  Bad voice JSON: {match.group(1)[:80]}")

    return components, voice_actions


# ── Main loop ───────────────────────────────────────────────────────────────

async def run_agent():
    # Spawn the persistent discli serve subprocess using the SAME interpreter
    # that's running this script (sys.executable + python -m discli). This
    # guarantees we use the dev venv's discli, not an older `discli` on PATH.
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "discli", "--json", "serve",
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
        channel_id = data.get("channel_id")
        if not channel_id:
            print("  Component missing channel_id")
            return

        payload = {"channel_id": channel_id}
        content = (data.get("content") or "").strip()
        has_embed = bool(data.get("embed"))
        if content:
            payload["content"] = content
        elif not has_embed:
            payload["content"] = "\u200b"  # zero-width space
        if has_embed:
            payload["embed"] = data["embed"]
        if data.get("components"):
            payload["components"] = data["components"]

        if data.get("message_id"):
            await serve_send("reply", message_id=data["message_id"], **payload)
        else:
            await serve_send("send", **payload)
        print(f"  Sent component to {channel_id}")

    # Map ```voice block actions → serve stdin action names
    VOICE_ACTION_MAP = {
        "connect": "voice_connect",
        "disconnect": "voice_disconnect",
        "move": "voice_move",
        "speak": "voice_speak",
        "play": "voice_play",
        "stop": "voice_stop",
        "pause": "voice_pause",
        "resume": "voice_resume",
        "listen_start": "voice_listen_start",
        "listen_stop": "voice_listen_stop",
        "status": "voice_status",
        "set_config": "voice_set_config",
    }

    async def dispatch_voice(data: dict):
        """Translate a ```voice block into a serve voice_* action."""
        action = data.pop("action", None)
        mapped = VOICE_ACTION_MAP.get(action)
        if not mapped:
            print(f"  Unknown voice action: {action}")
            return
        if "channel_id" not in data and action != "set_config":
            print(f"  Voice action '{action}' missing channel_id")
            return
        await serve_send(mapped, **data)
        print(f"  Voice {action} → {data.get('channel_id', '')}")

    options = sdk.ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        model="claude-haiku-4-5",
        max_turns=8,
    )

    async with sdk.ClaudeSDKClient(options) as claude:
        print("Claude session connected.")

        async def ask(prompt: str):
            await claude.query(prompt)
            full_response = ""
            async for msg in claude.receive_response():
                if isinstance(msg, sdk.AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, sdk.TextBlock) and block.text.strip():
                            full_response = block.text.strip()
                            print(f"  Claude: {full_response[:200]}")
                elif isinstance(msg, sdk.ResultMessage):
                    cost = f"${msg.total_cost_usd:.4f}" if msg.total_cost_usd else "n/a"
                    print(f"  Done. Cost: {cost}")
            components, voice_actions = extract_blocks(full_response)
            for comp in components:
                await send_component(comp)
            for va in voice_actions:
                await dispatch_voice(va)

        # Forward stderr from the serve subprocess so its diagnostic prints
        # (voice pipeline, etc.) are visible alongside the agent's own logs.
        async def _drain_stderr():
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                sys.stderr.write(f"[serve] {line.decode(errors='replace')}")
                sys.stderr.flush()

        asyncio.create_task(_drain_stderr())

        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode(errors="replace").strip()
                if not decoded:
                    continue
                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError:
                    # Diagnostic prints from serve/voice engine — surface them.
                    print(f"[serve] {decoded}")
                    continue
                event = data.get("event")

                # ── Ready / connection ──
                if event == "ready":
                    print(f"Bot online as {data.get('bot_name')}")
                elif event == "disconnected":
                    print("⚠ Disconnected")
                elif event == "resumed":
                    print("✓ Reconnected")
                elif event == "error":
                    print(f"ERROR: {data.get('message')}")
                elif event == "response":
                    if data.get("error"):
                        print(f"  Serve error: {data['error']}")

                # ── Text messages (@mention or DM) ──
                elif event == "message":
                    if data.get("is_bot"):
                        continue
                    if not data.get("mentions_bot") and not data.get("is_dm"):
                        continue

                    channel_id = data["channel_id"]
                    message_id = data["message_id"]
                    author = data["author"]
                    content = data["content"]
                    print(f"[{author}] {content[:120]}")

                    await serve_send("typing_start", channel_id=channel_id)
                    prompt = f"""A user mentioned you in Discord. Respond to them.

Channel ID: {channel_id}
Message ID: {message_id}
Author: {author} (ID: {data.get('author_id', '')})
Message: {content}

Reply using:  discli message reply {channel_id} {message_id} "your response"
Or output a ```component block for buttons / selects / modals."""
                    await ask(prompt)
                    await serve_send("typing_stop", channel_id=channel_id)

                # ── Voice: transcribed speech ──
                elif event == "voice_speech_detected":
                    channel_id = data["channel_id"]
                    text = (data.get("text") or "").strip()
                    member = data.get("member", "someone")
                    confidence = data.get("confidence", 0.0)
                    if not text or confidence < 0.5:
                        continue
                    print(f"🎤 [{member}] {text} (conf={confidence:.2f})")
                    prompt = f"""Someone spoke in a voice channel and you heard them.

Voice channel ID: {channel_id}
Speaker: {member}
Transcript: {text}

Respond by emitting a ```voice block with action "speak":
```voice
{{"action": "speak", "channel_id": "{channel_id}", "text": "your reply", "tts": "{TTS_PROVIDER}", "voice": "{TTS_VOICE}"}}
```
Keep it short (1–2 sentences), conversational, and don't read punctuation aloud."""
                    await ask(prompt)

                # ── Voice: join/leave/move ──
                elif event == "voice_state":
                    action = data.get("action")
                    member = data.get("member")
                    channel = data.get("channel")
                    print(f"🔊 {member} {action} {channel or ''}")

                elif event == "voice_audio_received":
                    # Raw audio chunks — normally consumed by the STT pipeline.
                    pass

                # ── Component interactions (buttons / selects / pickers) ──
                elif event == "component_interaction":
                    cid = data.get("custom_id", "")
                    itk = data["interaction_token"]
                    user = data.get("user", "someone")
                    values = data.get("values", [])
                    channel_id = str(data.get("channel_id", ""))
                    message_id = data.get("message_id", "")
                    print(f"Component: {cid} by {user}, values={values}")

                    # Special: button custom_id "modal:<id>" opens a registered modal
                    if cid.startswith("modal:"):
                        modal_id = cid[6:]
                        modal_def = modal_registry.get(modal_id)
                        if modal_def:
                            await serve_send(
                                "modal_send",
                                interaction_token=itk,
                                title=modal_def.get("title", "Form"),
                                custom_id=modal_def.get("custom_id", modal_id),
                                fields=modal_def.get("fields", []),
                            )
                            print(f"  Opened modal: {modal_def.get('title')}")
                        else:
                            await serve_send(
                                "interaction_respond",
                                interaction_token=itk,
                                content="Form not found.",
                                ephemeral=True,
                            )
                        continue

                    # Acknowledge immediately, then let Claude handle the logic
                    await serve_send(
                        "interaction_respond",
                        interaction_token=itk,
                        content="Processing…",
                        ephemeral=True,
                    )
                    prompt = f"""{user} interacted with a component.

Custom ID: {cid}
Values: {json.dumps(values)}
Channel ID: {channel_id}
Message ID: {message_id}

Respond appropriately. Use discli for text or a ```component block for more UI."""
                    await ask(prompt)

                # ── Modal submissions ──
                elif event == "modal_submit":
                    itk = data["interaction_token"]
                    fields = data.get("fields", {})
                    user = data.get("user", "someone")
                    channel_id = str(data.get("channel_id", ""))
                    custom_id = data.get("custom_id", "")
                    print(f"Modal {custom_id} from {user}: {fields}")

                    await serve_send(
                        "interaction_followup",
                        interaction_token=itk,
                        content="Got it — thanks!",
                        ephemeral=True,
                    )
                    prompt = f"""{user} submitted a form.

Custom ID: {custom_id}
Fields: {json.dumps(fields, indent=2)}
Channel ID: {channel_id}

Thank them and show the submission back as an embed, e.g.:
discli message send {channel_id} "" --embed-title "Form received" --embed-color 57F287 --embed-field "Field::Value::false" ..."""
                    await ask(prompt)

                # ── Slash commands (if you register any) ──
                elif event == "slash_command":
                    itk = data["interaction_token"]
                    command = data.get("command", "")
                    args = data.get("args", {})
                    user = data.get("user", "someone")
                    channel_id = str(data.get("channel_id", ""))
                    print(f"/{command} from {user}: {args}")

                    prompt = f"""Slash command /{command} from {user}.
Args: {json.dumps(args)}
Channel ID: {channel_id}

Respond in the channel. Send a message or an embed with discli."""
                    await ask(prompt)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            proc.terminate()


def main():
    print("Starting Claude-powered Discord agent (voice + interactive)...")
    print(f"Loading instructions from: {INSTRUCTIONS_PATH}")
    print("Listening for messages, voice, and component events...\n")
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
