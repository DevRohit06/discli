"""
AI support agent powered by Claude via the Claude Agent SDK.

Listens for @mentions, sends the conversation to Claude with discli
available as a tool, and lets Claude autonomously respond on Discord.

Uses your existing Claude Code authentication — no API key needed.
Keeps a single persistent Claude Code session for all messages.
Loads agent instructions from agents/discord-agent.md.

Requirements:
    pip install discord-cli-agent claude-agent-sdk

Usage:
    discli config set token YOUR_BOT_TOKEN
    python examples/claude_agent.py
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path

# Allow running inside a Claude Code session
os.environ.pop("CLAUDECODE", None)

import claude_agent_sdk as sdk

# Load instructions from file
INSTRUCTIONS_PATH = Path(__file__).parent.parent / "agents" / "discord-agent.md"
AGENT_INSTRUCTIONS = INSTRUCTIONS_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = f"""{AGENT_INSTRUCTIONS}

## Your Persona

You are a helpful, concise, and friendly Discord support agent.
If you don't know something, say so.
Always reply to the specific message that triggered you.
"""


async def run_agent():
    """Run the Discord agent with a persistent Claude session."""
    options = sdk.ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=5,
    )

    async with sdk.ClaudeSDKClient(options) as client:
        print("Claude session connected.")

        # Start listening for Discord events
        process = subprocess.Popen(
            ["discli", "--json", "listen", "--events", "messages"],
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

                channel_id = event["channel_id"]
                message_id = event["message_id"]
                content = event["content"]
                author = event["author"]

                print(f"[{author}] {content}")

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

                # Send to the persistent Claude session
                await client.query(prompt)

                async for message in client.receive_response():
                    if isinstance(message, sdk.AssistantMessage):
                        for block in message.content:
                            if isinstance(block, sdk.TextBlock):
                                print(f"  Claude: {block.text}")
                    elif isinstance(message, sdk.ResultMessage):
                        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
                        print(f"  Done. Cost: {cost}")

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            process.terminate()


def main():
    print("Starting Claude-powered Discord agent...")
    print(f"Loading instructions from: {INSTRUCTIONS_PATH}")
    print("Listening for @mentions...\n")
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
