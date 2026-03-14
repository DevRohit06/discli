"""
Echo bot using discli serve.

Demonstrates the bidirectional JSONL protocol: reads events from stdout,
sends commands via stdin, and uses streaming edits for responses.

Requirements:
    pip install discord-cli-agent

Usage:
    discli config set token YOUR_BOT_TOKEN
    python examples/serve_bot.py
"""

import asyncio
import json
import sys
from pathlib import Path

SLASH_COMMANDS = [
    {"name": "echo", "description": "Echo your message back",
     "params": [{"name": "message", "type": "string", "description": "Text to echo"}]},
    {"name": "ping", "description": "Check if the bot is alive"},
]


async def main():
    # Write slash commands to temp file
    import tempfile
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

    async def send_cmd(action: str, **kwargs) -> None:
        nonlocal req_counter
        req_counter += 1
        cmd = {"action": action, "req_id": str(req_counter), **kwargs}
        proc.stdin.write((json.dumps(cmd) + "\n").encode())
        await proc.stdin.drain()

    async def stream_response(channel_id: str, reply_to: str, text: str) -> None:
        """Send a response using streaming edits (simulates token-by-token)."""
        await send_cmd("stream_start", channel_id=channel_id, reply_to=reply_to)
        # Wait for stream_id in response
        await asyncio.sleep(0.5)
        # Stream word by word
        words = text.split()
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            await send_cmd("stream_chunk", stream_id=stream_response.last_stream_id, content=chunk)
            await asyncio.sleep(0.1)  # Simulate thinking
        await send_cmd("stream_end", stream_id=stream_response.last_stream_id)

    stream_response.last_stream_id = None

    print("Starting serve bot...")

    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            data = json.loads(line.decode().strip())
            event = data.get("event")

            if event == "ready":
                print(f"Bot connected as {data['bot_name']}")

            elif event == "response":
                # Track stream IDs from responses
                if "stream_id" in data:
                    stream_response.last_stream_id = data["stream_id"]

            elif event == "message":
                # Skip bot's own messages
                if data.get("is_bot"):
                    continue

                content = data["content"]
                channel_id = data["channel_id"]
                message_id = data["message_id"]
                author = data["author"]

                if data.get("mentions_bot"):
                    print(f"[{author}] {content}")
                    # Show typing, then reply
                    await send_cmd("typing_start", channel_id=channel_id)
                    await asyncio.sleep(1)
                    await send_cmd("typing_stop", channel_id=channel_id)
                    await send_cmd("reply",
                                   channel_id=channel_id,
                                   message_id=message_id,
                                   content=f"You said: {content}")

            elif event == "slash_command":
                command = data["command"]
                interaction_token = data["interaction_token"]
                print(f"Slash command: /{command} from {data['user']}")

                if command == "echo":
                    msg = data["args"].get("message", "(empty)")
                    await send_cmd("interaction_followup",
                                   interaction_token=interaction_token,
                                   content=f"Echo: {msg}")
                elif command == "ping":
                    await send_cmd("interaction_followup",
                                   interaction_token=interaction_token,
                                   content="Pong!")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        proc.terminate()
        Path(slash_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
