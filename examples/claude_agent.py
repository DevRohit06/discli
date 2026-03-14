"""
AI support agent powered by Claude via the Claude Agent SDK.

Listens for @mentions, sends the conversation to Claude with discli
available as a tool, and lets Claude autonomously respond on Discord.

Uses your existing Claude Code authentication — no API key needed.

Requirements:
    pip install discord-cli-agent claude-agent-sdk

Usage:
    discli config set token YOUR_BOT_TOKEN
    python examples/claude_agent.py
"""

import asyncio
import json
import subprocess

import claude_agent_sdk as sdk


SYSTEM_PROMPT = """You are a helpful Discord support agent. You help users with their questions.

You have access to the Bash tool. Use it to run discli commands to interact with Discord:
- Reply to messages: discli message reply <channel_id> <message_id> "your response"
- Send messages: discli message send <channel_id> "your message"
- Show typing: discli typing <channel_id>
- Create threads: discli thread create <channel_id> <message_id> "thread name"
- Get message context: discli --json message list <channel_id> --limit 5
- Get a specific message: discli --json message get <channel_id> <message_id>

Be concise, helpful, and friendly. If you don't know something, say so.
Always reply to the specific message that mentioned you.
"""


async def handle_message(event: dict):
    """Send a Discord message to Claude and let it respond."""
    channel_id = event["channel_id"]
    message_id = event["message_id"]
    content = event["content"]
    author = event["author"]

    # Show typing while Claude thinks
    subprocess.Popen(
        ["discli", "typing", channel_id, "--duration", "10"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Get recent context
    context_result = subprocess.run(
        ["discli", "--json", "message", "list", channel_id, "--limit", "5"],
        capture_output=True,
        text=True,
    )
    recent_messages = context_result.stdout if context_result.returncode == 0 else "[]"

    prompt = f"""A user mentioned you in Discord. Respond to them.

Channel ID: {channel_id}
Message ID: {message_id}
Author: {author}
Message: {content}

Recent channel context:
{recent_messages}

Reply using: discli message reply {channel_id} {message_id} "your response"
"""

    options = sdk.ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=3,
    )

    async for message in sdk.query(prompt=prompt, options=options):
        if isinstance(message, sdk.AssistantMessage):
            for block in message.content:
                if isinstance(block, sdk.TextBlock):
                    print(f"  Claude: {block.text}")
        elif isinstance(message, sdk.ResultMessage):
            print(f"  Done. Cost: ${message.total_cost_usd:.4f}" if message.total_cost_usd else "  Done.")


def main():
    print("Starting Claude-powered Discord agent...")
    print("Listening for @mentions...\n")

    process = subprocess.Popen(
        ["discli", "listen", "--json", "--events", "messages"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            event = json.loads(line)

            if not event.get("mentions_bot"):
                continue

            author = event["author"]
            content = event["content"]
            print(f"[{author}] {content}")

            asyncio.run(handle_message(event))

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
