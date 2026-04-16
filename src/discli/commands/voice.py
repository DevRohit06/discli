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
                if event.get("event") == "voice_transcription":
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
