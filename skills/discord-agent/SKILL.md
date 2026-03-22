---
name: discord-agent
description: "Build AI-powered Discord agents using discli + Claude/OpenAI. Scaffolds agents that listen for mentions, maintain conversation context, use streaming responses, and handle slash commands. Works with Claude Agent SDK, Anthropic API, or OpenAI API."
---

# Discord AI Agent Builder

Build AI-powered Discord bots that use LLMs to respond intelligently. Combines `discli serve` with Claude or OpenAI for autonomous Discord agents.

## When to Use

Use this skill when the user wants to:
- Build an AI chatbot for Discord
- Create an agent that responds to @mentions with LLM-generated answers
- Wire up Claude or OpenAI to a Discord bot
- Build a support agent, Q&A bot, or conversational assistant

## Architecture Options

### Option A: Claude Agent SDK (Recommended)

Uses `claude-agent-sdk` — the simplest approach. Claude can call discli commands directly as tools.

```python
import asyncio
import json
import os
import subprocess
from pathlib import Path

os.environ.pop("CLAUDECODE", None)  # Allow running inside Claude Code

import claude_agent_sdk as sdk

SYSTEM_PROMPT = """You are a helpful Discord assistant. You have access to discli commands via Bash.

Key commands:
- discli message reply <channel_id> <message_id> "response" — reply to a message
- discli message send <channel_id> "text" — send a message
- discli --json message list <channel_id> --limit 5 — get recent context

Always reply to the specific message that triggered you.
Keep responses concise and friendly.
"""


async def run_agent():
    options = sdk.ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=5,
    )

    async with sdk.ClaudeSDKClient(options) as client:
        process = subprocess.Popen(
            ["discli", "--json", "listen", "--events", "messages"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        try:
            for line in process.stdout:
                event = json.loads(line.strip())
                if not event.get("mentions_bot"):
                    continue

                # Show typing while thinking
                subprocess.Popen(
                    ["discli", "typing", event["channel_id"], "--duration", "15"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

                prompt = f"""User @mentioned you in Discord.
Channel ID: {event['channel_id']}
Message ID: {event['message_id']}
Author: {event['author']}
Message: {event['content']}

Reply to this message using discli."""

                await client.query(prompt)
                async for msg in client.receive_response():
                    pass  # Claude handles the reply via tool use

        except KeyboardInterrupt:
            pass
        finally:
            process.terminate()


if __name__ == "__main__":
    asyncio.run(run_agent())
```

### Option B: Anthropic API + discli serve (Full control)

Direct API calls with streaming responses via discli serve.

```python
import asyncio
import json
import tempfile
from pathlib import Path

import anthropic

SYSTEM_PROMPT = "You are a helpful Discord assistant. Be concise and friendly."
MODEL = "claude-sonnet-4-20250514"

# Per-user conversation history
conversations: dict[str, list] = {}


async def main():
    api = anthropic.Anthropic()

    proc = await asyncio.create_subprocess_exec(
        "discli", "--json", "serve", "--status", "online",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    req_counter = 0
    last_stream_id = None

    async def send(action: str, **kwargs):
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

            if event.get("event") == "response" and "stream_id" in event:
                last_stream_id = event["stream_id"]
                continue

            if event.get("event") != "message" or event.get("is_bot"):
                continue
            if not event.get("mentions_bot"):
                continue

            channel_id = event["channel_id"]
            message_id = event["message_id"]
            user_id = event["author_id"]
            content = event["content"]

            # Maintain conversation history per user
            if user_id not in conversations:
                conversations[user_id] = []
            conversations[user_id].append({"role": "user", "content": content})
            # Keep last 10 turns
            conversations[user_id] = conversations[user_id][-20:]

            # Start streaming response
            await send("stream_start", channel_id=channel_id, reply_to=message_id)
            await asyncio.sleep(0.3)  # Wait for stream_id

            # Call Claude with streaming
            with api.messages.stream(
                model=MODEL,
                system=SYSTEM_PROMPT,
                messages=conversations[user_id],
                max_tokens=1024,
            ) as stream:
                full_response = ""
                for text in stream.text_stream:
                    full_response += text
                    if last_stream_id:
                        await send("stream_chunk", stream_id=last_stream_id, content=text)

            if last_stream_id:
                await send("stream_end", stream_id=last_stream_id)

            # Save assistant response to history
            conversations[user_id].append({"role": "assistant", "content": full_response})

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
```

### Option C: OpenAI API + discli serve

Same pattern with OpenAI.

```python
import asyncio
import json
from openai import OpenAI

SYSTEM_PROMPT = "You are a helpful Discord assistant. Be concise and friendly."
MODEL = "gpt-4o"
conversations: dict[str, list] = {}


async def main():
    api = OpenAI()

    proc = await asyncio.create_subprocess_exec(
        "discli", "--json", "serve", "--status", "online",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )

    req_counter = 0
    last_stream_id = None

    async def send(action: str, **kwargs):
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

            if event.get("event") == "response" and "stream_id" in event:
                last_stream_id = event["stream_id"]
                continue

            if event.get("event") != "message" or event.get("is_bot"):
                continue
            if not event.get("mentions_bot"):
                continue

            user_id = event["author_id"]
            if user_id not in conversations:
                conversations[user_id] = []
            conversations[user_id].append({"role": "user", "content": event["content"]})
            conversations[user_id] = conversations[user_id][-20:]

            await send("stream_start", channel_id=event["channel_id"], reply_to=event["message_id"])
            await asyncio.sleep(0.3)

            stream = api.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id],
                max_tokens=1024,
                stream=True,
            )

            full = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full += delta
                if last_stream_id and delta:
                    await send("stream_chunk", stream_id=last_stream_id, content=delta)

            if last_stream_id:
                await send("stream_end", stream_id=last_stream_id)

            conversations[user_id].append({"role": "assistant", "content": full})

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
```

## Key Patterns

### Conversation History
- Store per-user: `conversations[user_id] = [{"role": "user", "content": ...}, ...]`
- Trim to last N turns to stay within context limits
- Include recent channel context via `message_list` for richer replies

### Streaming Responses
1. `stream_start` → get `stream_id` from response event
2. `stream_chunk` with each LLM token
3. `stream_end` to finalize
- discli auto-edits the message every 1.5s so users see live typing
- Messages over 2000 chars are auto-split

### Thread-per-conversation
Create a thread for each user interaction to keep conversations organized:
```python
await send("thread_create", channel_id=channel_id, message_id=message_id, name=f"Support: {author}")
# Then send all replies to the thread instead
await send("thread_send", thread_id=thread_id, content=response)
```

### Rich Embeds for Structured Responses
```python
await send("send", channel_id=channel_id, content="Here's what I found:", embed={
    "title": "Search Results",
    "color": "5865F2",
    "fields": [
        {"name": "Result 1", "value": "Description...", "inline": False},
        {"name": "Result 2", "value": "Description...", "inline": False},
    ],
    "footer": "Powered by AI",
})
```

## Guidelines

- Always check `mentions_bot` — don't respond to every message
- Use `typing_start` before LLM calls so users see the bot is thinking
- Keep system prompts concise — the LLM doesn't need the full discli reference
- Use streaming for any response that might take >2 seconds
- Handle `disconnected`/`resumed` events for connection awareness
- Set appropriate `max_tokens` to avoid excessively long responses
- Rate limit per-user to prevent abuse
