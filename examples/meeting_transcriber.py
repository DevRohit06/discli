"""
Meeting transcription example for discli, with Claude-powered summary on exit.

Joins a server voice channel, transcribes every speaker live with their
display names, appends to ~/.discli/transcripts/meeting-<timestamp>.md, and
asks Claude (via the Agent SDK) to summarize the meeting when you press Ctrl+C.

Bot tokens only — Discord's API restricts application bots to server voice
channels, so DM and group-DM voice calls aren't supported here. Test in a
server voice channel.

Requires the DAVE-aware patches in ``discli.voice_engine`` (applied
automatically by ``VoiceEngine.listen_start``).

Setup:
    discli config set token YOUR_BOT_TOKEN
    export DEEPGRAM_API_KEY=...                 # or use --stt openai

Usage:
    python examples/meeting_transcriber.py <voice_channel_id>
    python examples/meeting_transcriber.py 1016638171854938152 --stt openai

The summary on exit uses your existing Claude Code authentication — no
Anthropic API key required.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow running inside a Claude Code session.
os.environ.pop("CLAUDECODE", None)

# Force UTF-8 on Windows so non-ASCII transcript text doesn't crash the print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import discord
import claude_agent_sdk as sdk

from discli.config import load_config
from discli.voice_engine import VoiceEngine


SUMMARY_SYSTEM_PROMPT = """You are summarizing a Discord voice-channel meeting transcript.

Output GitHub-flavored markdown with exactly these sections, in this order:

## Summary
Two or three sentences capturing the meeting's purpose and outcome.

## Key decisions
Bulleted list of decisions made. Omit the section entirely if none.

## Action items
Bulleted list. Include the owner (display name as written in the transcript) if
mentioned, and a target date or deadline if mentioned.

## Open questions
Bulleted list of unresolved questions. Omit the section entirely if none.

Be concise. Refer to participants by the display names exactly as written in
the transcript."""


def _resolve_token() -> str | None:
    """Find a Discord bot token: env var first, then ~/.discli/config.json."""
    return os.environ.get("DISCORD_TOKEN") or load_config().get("token")


async def run(channel_id: int, stt_provider: str) -> None:
    token = _resolve_token()
    if not token:
        sys.exit(
            "No Discord bot token found. Run 'discli config set token <TOKEN>' "
            "or set the DISCORD_TOKEN environment variable."
        )

    # `members` intent so display-name lookups work for everyone in the call,
    # not just the bot's recent cache.
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    ready = asyncio.Event()

    @client.event
    async def on_ready():
        print(f"Connected as {client.user} ({client.user.id})", flush=True)
        ready.set()

    client_task = asyncio.create_task(client.start(token))
    await ready.wait()

    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            sys.exit(f"Channel {channel_id} not found.")
        except discord.Forbidden:
            sys.exit(f"Bot does not have access to channel {channel_id}.")
        except discord.HTTPException as exc:
            sys.exit(f"Discord API error fetching channel {channel_id}: {exc!r}")

    if not isinstance(channel, discord.VoiceChannel):
        sys.exit(
            f"Channel {channel_id} is a {type(channel).__name__}, not a server "
            f"voice channel. Bot tokens cannot join DM or group voice calls."
        )

    started_at = datetime.now()
    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    transcript_dir = Path.home() / ".discli" / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    path = transcript_dir / f"meeting-{stamp}.md"

    with path.open("w", encoding="utf-8") as f:
        f.write(f"# Meeting transcript — {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"- **Channel:** #{channel.name} ({channel.guild.name})\n")
        f.write(f"- **Bot:** {client.user}\n\n")
        f.write("## Transcript\n\n")

    engine = VoiceEngine(config={"stt_provider": stt_provider})
    transcript_lines: list[str] = []
    name_cache: dict[int, str] = {}

    def resolve_name(uid: int) -> str:
        cached = name_cache.get(uid)
        if cached:
            return cached
        member = channel.guild.get_member(uid)
        if member is not None:
            name = member.display_name
        else:
            user = client.get_user(uid)
            name = user.display_name if user else f"user-{uid}"
        name_cache[uid] = name
        return name

    def on_event(event: dict) -> None:
        if event.get("event") != "voice_speech_detected":
            return
        if not event.get("is_final"):
            return
        text = (event.get("text") or "").strip()
        if not text:
            return
        try:
            uid = int(event.get("user_id") or 0)
        except (TypeError, ValueError):
            return
        if uid == client.user.id:
            return
        name = resolve_name(uid)
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"- **[{ts}] {name}:** {text}"
        transcript_lines.append(line)
        print(line, flush=True)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as exc:
            print(f"[transcript] write error: {exc!r}", file=sys.stderr, flush=True)

    engine.set_event_handler(on_event)

    await engine.connect(channel)
    await engine.listen_start(channel.guild.id)
    print(f"\nListening to #{channel.name}. Transcript: {path}")
    print("Press Ctrl+C to stop and generate a summary.\n", flush=True)

    try:
        while True:
            await asyncio.sleep(1.0)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        print("\nStopping listener…", flush=True)
        try:
            engine.listen_stop(channel.guild.id)
        except Exception as exc:
            print(f"listen_stop error: {exc!r}", file=sys.stderr, flush=True)
        try:
            await engine.disconnect(channel.guild.id)
        except Exception as exc:
            print(f"disconnect error: {exc!r}", file=sys.stderr, flush=True)

        if transcript_lines:
            print(f"Generating summary from {len(transcript_lines)} line(s)…", flush=True)
            try:
                await _write_summary(path, transcript_lines, channel)
            except Exception as exc:
                print(f"Summary error: {exc!r}", file=sys.stderr, flush=True)
        else:
            print("No transcript captured — skipping summary.", flush=True)

        try:
            await client.close()
        except Exception as exc:
            print(f"client.close error: {exc!r}", file=sys.stderr, flush=True)
        client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"client_task shutdown error: {exc!r}", file=sys.stderr, flush=True)


async def _write_summary(
    path: Path, lines: list[str], channel: discord.VoiceChannel
) -> None:
    transcript = "\n".join(lines)
    prompt = (
        f"Channel: #{channel.name} in {channel.guild.name}\n\n"
        f"Transcript:\n{transcript}"
    )

    options = sdk.ClaudeAgentOptions(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        model="claude-haiku-4-5",
        max_turns=2,
    )

    parts: list[str] = []
    async with sdk.ClaudeSDKClient(options) as claude:
        await claude.query(prompt)
        async for msg in claude.receive_response():
            if isinstance(msg, sdk.AssistantMessage):
                for block in msg.content:
                    if isinstance(block, sdk.TextBlock) and block.text:
                        parts.append(block.text)
            elif isinstance(msg, sdk.ResultMessage):
                if msg.total_cost_usd:
                    print(f"Summary cost: ${msg.total_cost_usd:.4f}", flush=True)

    summary = "".join(parts).strip()
    if not summary:
        print("Claude returned an empty summary.", flush=True)
        return

    with path.open("a", encoding="utf-8") as f:
        f.write("\n---\n\n")
        f.write(summary + "\n")

    print("\n=== Meeting Summary ===\n", flush=True)
    print(summary, flush=True)
    print(f"\nFull transcript + summary saved to: {path}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Live meeting transcription for a Discord server voice channel."
    )
    p.add_argument("channel_id", type=int, help="Server voice channel ID")
    p.add_argument(
        "--stt",
        default=os.environ.get("DISCLI_STT", "deepgram"),
        choices=["deepgram", "openai"],
        help="STT provider (default: deepgram; env: DISCLI_STT)",
    )
    args = p.parse_args()

    try:
        asyncio.run(run(args.channel_id, args.stt))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
