"""
Support agent that creates a thread for each support request.

When someone mentions the bot, it:
1. Creates a thread from that message
2. Replies inside the thread
3. Continues the conversation within the thread

Usage:
    python examples/thread_support_agent.py
"""

import json
import subprocess


def run_discli(*args) -> dict | None:
    """Run a discli command and return parsed JSON output."""
    result = subprocess.run(
        ["discli", "--json", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr.strip()}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def get_ai_response(content: str) -> str:
    """Replace with your actual AI call."""
    return f"I've received your support request. Let me help you with: {content[:100]}"


def main():
    print("Starting thread support agent...")
    active_threads: set[str] = set()

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
            channel_id = event["channel_id"]
            message_id = event["message_id"]
            content = event["content"]
            author = event["author"]

            # New support request: bot is mentioned in a regular channel
            if event.get("mentions_bot") and channel_id not in active_threads:
                print(f"New support request from {author}: {content}")

                # Create a thread
                thread = run_discli(
                    "thread", "create", channel_id, message_id,
                    f"Support - {author}"
                )
                if thread:
                    thread_id = thread["id"]
                    active_threads.add(thread_id)

                    # Reply in the thread
                    response = get_ai_response(content)
                    run_discli("thread", "send", thread_id, response)
                    print(f"Created thread {thread_id}, replied.")

            # Ongoing conversation inside an active thread
            elif channel_id in active_threads:
                print(f"Follow-up from {author} in thread {channel_id}: {content}")

                subprocess.Popen(
                    ["discli", "typing", channel_id, "--duration", "3"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                response = get_ai_response(content)
                run_discli("thread", "send", channel_id, response)
                print(f"Replied in thread {channel_id}")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
