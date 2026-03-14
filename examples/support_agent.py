"""
Support agent that listens for @mentions and replies with help.

Uses discli as a subprocess — no Discord library needed in your agent code.
Pipe `discli listen --json` and call `discli message reply` to respond.

Usage:
    python examples/support_agent.py
"""

import json
import subprocess
import sys


def get_response(message: str) -> str:
    """Replace this with your AI model call."""
    message_lower = message.lower()
    if "help" in message_lower:
        return "Hi! I'm the support bot. How can I help you today?"
    if "pricing" in message_lower:
        return "Check out our pricing page at example.com/pricing"
    if "bug" in message_lower or "issue" in message_lower:
        return "Sorry to hear that! Could you describe the issue in detail? I'll create a thread for us."
    return "Thanks for reaching out! Let me look into that for you."


def show_typing(channel_id: str):
    """Trigger typing indicator while the agent thinks."""
    subprocess.Popen(
        ["discli", "typing", channel_id, "--duration", "3"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def reply(channel_id: str, message_id: str, text: str):
    """Reply to a message."""
    subprocess.run(
        ["discli", "message", "reply", channel_id, message_id, text],
        capture_output=True,
    )


def main():
    print("Starting support agent...")
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

            show_typing(channel_id)
            response = get_response(content)
            reply(channel_id, message_id, response)

            print(f"[BOT] {response}")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
