"""
Simple moderation bot that watches for keywords and takes action.

Monitors messages for banned words, warns the user, and deletes
the message. Escalates to kick after repeated violations.

Usage:
    python examples/moderation_bot.py
"""

import json
import subprocess
from collections import defaultdict

BANNED_WORDS = {"spam", "scam", "phishing"}
WARN_THRESHOLD = 3


def run_discli(*args):
    """Run a discli command."""
    subprocess.run(
        ["discli", *args],
        capture_output=True,
        text=True,
    )


def main():
    print("Starting moderation bot...")
    violations: dict[str, int] = defaultdict(int)

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
            content = event["content"].lower()
            author = event["author"]
            author_id = event["author_id"]
            channel_id = event["channel_id"]
            message_id = event["message_id"]
            server = event.get("server", "")

            # Check for banned words
            found = [w for w in BANNED_WORDS if w in content]
            if not found:
                continue

            violations[author_id] += 1
            count = violations[author_id]

            print(f"Violation #{count} by {author}: {found}")

            # Delete the message
            run_discli("message", "delete", channel_id, message_id)

            if count >= WARN_THRESHOLD:
                # Kick after threshold
                run_discli("member", "kick", server, author_id,
                           "--reason", f"Repeated violations ({count}x)")
                run_discli("message", "send", channel_id,
                           f"{author} has been kicked for repeated violations.")
                print(f"Kicked {author}")
                del violations[author_id]
            else:
                # Warn
                remaining = WARN_THRESHOLD - count
                run_discli("message", "send", channel_id,
                           f"{author}, your message was removed. "
                           f"{remaining} warning(s) remaining before kick.")
                print(f"Warned {author} ({remaining} remaining)")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
