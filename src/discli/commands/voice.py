import asyncio

import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_guild


def _resolve_voice_channel(client, channel_identifier: str, server: str | None):
    """Resolve a voice channel by name or ID, optionally scoped to a server."""
    if server:
        guilds = [resolve_guild(client, server)]
    else:
        guilds = client.guilds

    # Try by ID first
    try:
        channel_id = int(channel_identifier)
        ch = client.get_channel(channel_id)
        if ch is not None and isinstance(ch, discord.VoiceChannel):
            return ch
    except ValueError:
        pass

    # Try by name
    for guild in guilds:
        for ch in guild.voice_channels:
            if ch.name.lower() == channel_identifier.lower():
                return ch

    raise click.ClickException(f"Voice channel not found: {channel_identifier}")


def _find_active_voice_guild(client, server: str | None):
    """Return the guild that has an active voice_client, or raise ClickException."""
    if server:
        guild = resolve_guild(client, server)
        if guild.voice_client is not None:
            return guild
        raise click.ClickException(f"No active voice connection in server: {server}")

    for guild in client.guilds:
        if guild.voice_client is not None:
            return guild

    raise click.ClickException(
        "No active voice connection found. Join a voice channel first with 'discli voice join'."
    )


@click.group("voice")
def voice_group():
    """Voice channel operations — join, speak, play, listen."""


@voice_group.command("join")
@click.argument("channel")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_join(ctx, channel, server):
    """Join a voice channel."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            ch = _resolve_voice_channel(client, channel, server)
            engine = VoiceEngine()
            vc = await engine.connect(ch)
            data = {
                "channel_id": str(ch.id),
                "channel_name": ch.name,
                "guild_id": str(ch.guild.id),
                "guild_name": ch.guild.name,
                "connected": True,
            }
            output(ctx, data, plain_text=f"Joined voice channel #{ch.name} in {ch.guild.name}")
            # Disconnect cleanly after the one-shot action
            await engine.disconnect(ch.guild.id)

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("leave")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_leave(ctx, server):
    """Leave the active voice channel."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client
            channel_name = vc.channel.name if vc.channel else "unknown"

            engine = VoiceEngine()
            # Register the existing connection so VoiceEngine can manage it
            engine.connections[guild.id] = vc
            await engine.disconnect(guild.id)

            data = {"guild_id": str(guild.id), "guild_name": guild.name, "disconnected": True}
            output(ctx, data, plain_text=f"Left voice channel #{channel_name} in {guild.name}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("speak")
@click.argument("text")
@click.option("--server", default=None, help="Server name or ID.")
@click.option("--voice", "voice_name", default="default", help="TTS voice name.")
@click.option("--speed", default=1.0, type=float, help="TTS speed multiplier.")
@click.pass_context
def voice_speak(ctx, text, server, voice_name, speed):
    """Speak text using TTS in the active voice channel."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            engine = VoiceEngine()
            engine.connections[guild.id] = vc

            await engine.speak(guild.id, text, voice=voice_name, speed=speed)

            data = {
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "text": text,
                "voice": voice_name,
                "speed": speed,
            }
            output(ctx, data, plain_text=f"Speaking in {guild.name}: {text!r}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("play")
@click.argument("source")
@click.option("--server", default=None, help="Server name or ID.")
@click.option("--volume", default=1.0, type=float, help="Playback volume (0.0–2.0).")
@click.pass_context
def voice_play(ctx, source, server, volume):
    """Play a file or URL in the active voice channel."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            engine = VoiceEngine(config={"playback_volume": volume})
            engine.connections[guild.id] = vc

            await engine.play(guild.id, source)

            data = {
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "source": source,
                "volume": volume,
            }
            output(ctx, data, plain_text=f"Playing {source!r} in {guild.name}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("stop")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_stop(ctx, server):
    """Stop current audio playback."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            engine = VoiceEngine()
            engine.connections[guild.id] = vc
            # Build minimal player so stop() works
            from discli.voice_engine import AudioPlayer
            player = AudioPlayer(vc)
            engine._players[guild.id] = player
            engine.stop(guild.id)

            data = {"guild_id": str(guild.id), "guild_name": guild.name, "stopped": True}
            output(ctx, data, plain_text=f"Stopped playback in {guild.name}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("pause")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_pause(ctx, server):
    """Pause current audio playback."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine, AudioPlayer

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            engine = VoiceEngine()
            engine.connections[guild.id] = vc
            player = AudioPlayer(vc)
            engine._players[guild.id] = player
            engine.pause(guild.id)

            data = {"guild_id": str(guild.id), "guild_name": guild.name, "paused": True}
            output(ctx, data, plain_text=f"Paused playback in {guild.name}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("resume")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_resume(ctx, server):
    """Resume paused audio playback."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine, AudioPlayer

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            engine = VoiceEngine()
            engine.connections[guild.id] = vc
            player = AudioPlayer(vc)
            engine._players[guild.id] = player
            engine.resume(guild.id)

            data = {"guild_id": str(guild.id), "guild_name": guild.name, "resumed": True}
            output(ctx, data, plain_text=f"Resumed playback in {guild.name}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("listen")
@click.option("--server", default=None, help="Server name or ID.")
@click.option(
    "--duration",
    default=0,
    type=int,
    help="Listen duration in seconds (0 = until Ctrl+C).",
)
@click.option("--continuous", is_flag=True, default=False, help="Keep listening after each transcription.")
@click.pass_context
def voice_listen(ctx, server, duration, continuous):
    """Listen to the active voice channel and print transcriptions."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            engine = VoiceEngine()
            engine.connections[guild.id] = vc

            transcriptions = []

            def on_event(event: dict):
                if event.get("event") == "voice_speech_detected":
                    entry = {
                        "user_id": event.get("user_id"),
                        "text": event.get("text"),
                        "confidence": event.get("confidence"),
                        "is_final": event.get("is_final"),
                    }
                    transcriptions.append(entry)
                    use_json = ctx.obj.get("use_json", False)
                    import json as json_mod
                    if use_json:
                        click.echo(json_mod.dumps(entry))
                    else:
                        click.echo(f"[{entry['user_id']}] {entry['text']}")

            engine.set_event_handler(on_event)
            await engine.listen_start(guild.id)

            try:
                if duration > 0:
                    await asyncio.sleep(duration)
                else:
                    # Run until Ctrl+C
                    while True:
                        await asyncio.sleep(0.5)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                engine.listen_stop(guild.id)

            data = {
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "transcriptions": transcriptions,
                "count": len(transcriptions),
            }
            if not transcriptions:
                output(ctx, data, plain_text="No transcriptions captured.")
            else:
                output(
                    ctx,
                    data,
                    plain_text=f"Captured {len(transcriptions)} transcription(s) in {guild.name}",
                )

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("capture")
@click.option("--server", default=None, help="Server name or ID.")
@click.option("--duration", default=10, type=int, help="Capture duration in seconds.")
@click.option(
    "--output-dir",
    default=None,
    help="Output directory (default: ~/.discli/debug-capture).",
)
@click.pass_context
def voice_capture(ctx, server, duration, output_dir):
    """Capture raw 48 kHz stereo PCM to WAV files (debug helper).

    Bypasses STT and writes one .wav per speaker containing exactly the PCM
    voice_recv delivered to the sink. Use this to confirm the bot is actually
    receiving audio — if the WAV is empty or only ~20 ms long, the problem is
    at the capture layer, not in STT/downmix.

    Privacy note: the output WAVs contain raw decoded audio of everyone who
    spoke in the channel during the capture window. Treat them like any
    voice recording — don't share without consent.
    """

    def action(client):
        async def _action(client):
            import threading
            import wave
            from pathlib import Path

            from discord.ext import voice_recv

            guild = _find_active_voice_guild(client, server)
            vc = guild.voice_client

            if not hasattr(vc, "listen"):
                raise click.ClickException(
                    "Active voice client doesn't support listening. "
                    "Reconnect via 'discli voice join' (uses VoiceRecvClient)."
                )

            # voice_recv raises if a sink is already attached. Stop the active
            # listener (e.g. from `discli voice listen` or a serve session)
            # before attaching the capture sink.
            if getattr(vc, "is_listening", lambda: False)():
                raise click.ClickException(
                    "Another listening session is already active on this voice "
                    "client. Stop it first ('discli voice listen' Ctrl+C, or "
                    "the equivalent serve action) before running capture."
                )

            out_dir = (
                Path(output_dir)
                if output_dir
                else (Path.home() / ".discli" / "debug-capture")
            )
            out_dir.mkdir(parents=True, exist_ok=True)

            buffers: dict[int, bytearray] = {}
            packet_counts: dict[int, int] = {}
            lock = threading.Lock()

            class _CaptureSink(voice_recv.AudioSink):
                def __init__(self) -> None:
                    super().__init__()

                def wants_opus(self) -> bool:
                    return False

                def write(self, user, data) -> None:
                    uid = user.id if user else 0
                    with lock:
                        buf = buffers.get(uid)
                        if buf is None:
                            buf = bytearray()
                            buffers[uid] = buf
                            packet_counts[uid] = 0
                        buf.extend(data.pcm)
                        packet_counts[uid] += 1

                def cleanup(self) -> None:
                    pass

            sink = _CaptureSink()
            vc.listen(sink)
            click.echo(
                f"Capturing for {duration}s in #{vc.channel.name}… "
                f"(have people talk now)",
                err=True,
            )

            try:
                await asyncio.sleep(duration)
            finally:
                for method in ("stop_recording", "stop_listening"):
                    fn = getattr(vc, method, None)
                    if callable(fn):
                        try:
                            fn()
                        except Exception:
                            pass
                        break

            results = []
            with lock:
                for uid, buf in buffers.items():
                    member = guild.get_member(uid)
                    safe_name = "".join(
                        c if c.isalnum() or c in "-_" else "_"
                        for c in (member.display_name if member else str(uid))
                    )
                    fpath = out_dir / f"{uid}-{safe_name}.wav"
                    with wave.open(str(fpath), "wb") as wf:
                        wf.setnchannels(2)
                        wf.setsampwidth(2)
                        wf.setframerate(48000)
                        wf.writeframes(bytes(buf))
                    # 48 kHz stereo int16 = 4 bytes per frame.
                    duration_ms = int(len(buf) / 4 / 48000 * 1000) if buf else 0
                    results.append(
                        {
                            "user_id": str(uid),
                            "user_name": str(member) if member else None,
                            "packets": packet_counts[uid],
                            "bytes": len(buf),
                            "duration_ms": duration_ms,
                            "path": str(fpath),
                        }
                    )

            data = {
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "duration_seconds": duration,
                "output_dir": str(out_dir),
                "speakers": results,
            }

            if not results:
                output(
                    ctx,
                    data,
                    plain_text=(
                        f"No audio captured in {duration}s. Sink received zero "
                        f"packets — voice_recv is not delivering PCM to the bot."
                    ),
                )
            else:
                lines = [f"Captured to {out_dir}:"]
                for r in results:
                    lines.append(
                        f"  - {r['user_name'] or r['user_id']}: "
                        f"{r['packets']} packets, {r['bytes']} bytes, "
                        f"~{r['duration_ms']} ms → {Path(r['path']).name}"
                    )
                output(ctx, data, plain_text="\n".join(lines))

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("where")
@click.argument("user")
@click.option("--server", default=None, help="Server name or ID to scope the search.")
@click.pass_context
def voice_where(ctx, user, server):
    """Find which voice channel a user is currently in."""

    def action(client):
        async def _action(client):
            guilds = [resolve_guild(client, server)] if server else client.guilds

            try:
                user_id = int(user)
            except ValueError:
                user_id = None

            matches = []
            for guild in guilds:
                for member_id, vs in guild.voice_states.items():
                    if user_id is not None and member_id != user_id:
                        continue
                    member = guild.get_member(member_id)
                    if user_id is None:
                        name = user.lstrip("@").lower()
                        if not member or (
                            member.name.lower() != name
                            and (member.display_name or "").lower() != name
                        ):
                            continue
                    ch = vs.channel
                    matches.append({
                        "user_id": str(member_id),
                        "user_name": str(member) if member else None,
                        "guild_id": str(guild.id),
                        "guild_name": guild.name,
                        "channel_id": str(ch.id) if ch else None,
                        "channel_name": ch.name if ch else None,
                        "self_mute": vs.self_mute,
                        "self_deaf": vs.self_deaf,
                        "mute": vs.mute,
                        "deaf": vs.deaf,
                    })

            if not matches:
                output(ctx, [], plain_text=f"User '{user}' is not in any voice channel.")
            else:
                plain = "\n".join(
                    f"{m['user_name'] or m['user_id']} — #{m['channel_name']} in {m['guild_name']}"
                    for m in matches
                )
                output(ctx, matches, plain_text=plain)

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("members")
@click.argument("channel")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_members(ctx, channel, server):
    """List members currently connected to a voice channel."""

    def action(client):
        async def _action(client):
            ch = _resolve_voice_channel(client, channel, server)
            members = []
            for member in ch.members:
                vs = member.voice
                members.append({
                    "user_id": str(member.id),
                    "user_name": str(member),
                    "display_name": member.display_name,
                    "self_mute": vs.self_mute if vs else False,
                    "self_deaf": vs.self_deaf if vs else False,
                    "mute": vs.mute if vs else False,
                    "deaf": vs.deaf if vs else False,
                })

            data = {
                "channel_id": str(ch.id),
                "channel_name": ch.name,
                "guild_id": str(ch.guild.id),
                "guild_name": ch.guild.name,
                "count": len(members),
                "members": members,
            }

            if not members:
                output(ctx, data, plain_text=f"#{ch.name} is empty.")
            else:
                plain = f"#{ch.name} ({len(members)} member{'s' if len(members) != 1 else ''}):\n" + "\n".join(
                    f"  - {m['display_name']} ({m['user_id']})" for m in members
                )
                output(ctx, data, plain_text=plain)

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("status")
@click.pass_context
def voice_status(ctx):
    """Show all active voice connections across servers."""

    def action(client):
        async def _action(client):
            connections = []
            for guild in client.guilds:
                vc = guild.voice_client
                if vc is not None:
                    connections.append(
                        {
                            "guild_id": str(guild.id),
                            "guild_name": guild.name,
                            "channel_id": str(vc.channel.id) if vc.channel else None,
                            "channel_name": vc.channel.name if vc.channel else None,
                            "is_playing": vc.is_playing(),
                            "is_paused": vc.is_paused(),
                        }
                    )

            if not connections:
                output(ctx, [], plain_text="No active voice connections.")
            else:
                plain_lines = []
                for c in connections:
                    state = "playing" if c["is_playing"] else ("paused" if c["is_paused"] else "idle")
                    plain_lines.append(
                        f"{c['guild_name']} — #{c['channel_name']} ({state})"
                    )
                output(ctx, connections, plain_text="\n".join(plain_lines))

        return _action(client)

    run_discord(ctx, action)
