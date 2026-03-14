"""
AI support agent powered by Claude via the Agent SDK.

Listens for @mentions, sends the message to Claude with discli
as a tool, and lets Claude respond and take actions on Discord.

Requirements:
    pip install claude-agent-sdk

Usage:
    export ANTHROPIC_API_KEY=your-key
    python examples/claude_agent.py
"""

import json
import subprocess

import claude_agent_sdk as agent_sdk


SYSTEM_PROMPT = """You are a helpful Discord support agent. You help users with their questions.

You have access to a Discord CLI tool called `discli`. Use it to:
- Reply to messages: discli message reply <channel_id> <message_id> "your response"
- Send messages: discli message send <channel_id> "your message"
- Show typing: discli typing <channel_id>
- Create threads: discli thread create <channel_id> <message_id> "thread name"
- Get message context: discli message list <channel_id> --limit 5 --json

Be concise, helpful, and friendly. If you don't know something, say so.
"""


def run_discli_tool(command: str) -> str:
    """Execute a discli command and return the output."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout or result.stderr


# Define discli as a tool for Claude
discli_tool = agent_sdk.Tool(
    name="discli",
    description="Run a discli command to interact with Discord. Pass the full command string.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The full discli command to run, e.g. 'discli message reply 123 456 \"hello\"'"
            }
        },
        "required": ["command"],
    },
    function=lambda command: run_discli_tool(command),
)


def handle_message(event: dict):
    """Send a Discord message to Claude and let it respond."""
    channel_id = event["channel_id"]
    message_id = event["message_id"]
    content = event["content"]
    author = event["author"]

    # Show typing while Claude thinks
    subprocess.Popen(
        ["discli", "typing", channel_id, "--duration", "5"],
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

    # Build the prompt
    user_prompt = f"""A user mentioned you in Discord. Respond using the discli tool.

Channel ID: {channel_id}
Message ID: {message_id}
Author: {author}
Message: {content}

Recent channel context:
{recent_messages}

Reply to the user's message using: discli message reply {channel_id} {message_id} "your response"
"""

    # Let Claude handle it
    response = agent_sdk.run(
        model="claude-sonnet-4-6",
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[discli_tool],
        max_turns=5,
    )

    print(f"Claude responded to {author}: {content[:50]}...")


def main():
    print("Starting Claude-powered Discord agent...")

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

            handle_message(event)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
