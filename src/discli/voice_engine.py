"""Core voice engine — manages voice connections, audio playback, and listening."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any, Callable

import discord

from discli.stt import STTError, STTProvider, TranscriptionResult, get_stt_provider
from discli.tts import TTSError, TTSProvider, get_tts_provider


class VoiceError(Exception):
    """Raised for voice operation failures."""


DEFAULT_CONFIG: dict[str, Any] = {
    "tts_provider": "elevenlabs",
    "tts_voice": "default",
    "stt_provider": "deepgram",
    "vad_threshold": 0.5,
    "silence_duration_ms": 800,
    "playback_volume": 1.0,
}


class AudioPlayer:
    """Queue-based audio player for a voice connection."""

    def __init__(self, voice_client: discord.VoiceClient, volume: float = 1.0) -> None:
        self._vc = voice_client
        self._volume = max(0.0, min(2.0, volume))
        self._queue: asyncio.Queue = asyncio.Queue()
        self._current_source = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Create the background player loop task."""
        self._task = asyncio.get_event_loop().create_task(self._player_loop())

    async def _player_loop(self) -> None:
        """Pop sources from queue and play them sequentially."""
        while True:
            source = await self._queue.get()
            if source is None:
                break

            wrapped = discord.PCMVolumeTransformer(source, volume=self._volume)
            self._current_source = wrapped

            done_event = asyncio.Event()

            def after_play(error: Exception | None) -> None:
                if error:
                    pass  # swallow playback errors; loop continues
                asyncio.get_event_loop().call_soon_threadsafe(done_event.set)

            self._vc.play(wrapped, after=after_play)
            await done_event.wait()
            self._current_source = None

    async def enqueue(self, source: discord.AudioSource) -> None:
        """Enqueue any AudioSource."""
        await self._queue.put(source)

    async def enqueue_file(self, path: str) -> None:
        """Enqueue audio from a local file via FFmpeg."""
        source = discord.FFmpegPCMAudio(path)
        await self._queue.put(source)

    async def enqueue_url(self, url: str) -> None:
        """Enqueue audio from a URL via FFmpeg with reconnect options."""
        before_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        source = discord.FFmpegPCMAudio(url, before_options=before_options)
        await self._queue.put(source)

    async def enqueue_pcm(self, pcm_data: bytes) -> None:
        """Enqueue raw PCM bytes piped through FFmpeg."""
        buf = BytesIO(pcm_data)
        source = discord.FFmpegPCMAudio(buf, pipe=True)
        await self._queue.put(source)

    def stop(self) -> None:
        """Stop current playback."""
        if self._vc.is_playing():
            self._vc.stop()

    def pause(self) -> None:
        """Pause current playback."""
        if self._vc.is_playing():
            self._vc.pause()

    def resume(self) -> None:
        """Resume paused playback."""
        if self._vc.is_paused():
            self._vc.resume()

    def set_volume(self, volume: float) -> None:
        """Set playback volume, clamped to [0.0, 2.0]."""
        self._volume = max(0.0, min(2.0, volume))
        if self._current_source is not None:
            self._current_source.volume = self._volume

    @property
    def is_playing(self) -> bool:
        return self._vc.is_playing()

    async def close(self) -> None:
        """Signal the player loop to stop and await it."""
        await self._queue.put(None)
        if self._task is not None:
            await self._task
            self._task = None


class AudioListener:
    """Listens to voice channel audio, segments by VAD, feeds to STT."""

    def __init__(
        self,
        voice_client: discord.VoiceClient,
        stt: STTProvider,
        vad_threshold: float,
        silence_duration_ms: int,
        on_transcription: Callable[[str, TranscriptionResult], None],
    ) -> None:
        self._vc = voice_client
        self._stt = stt
        self._vad_threshold = vad_threshold
        self._silence_duration_ms = silence_duration_ms
        self._on_transcription = on_transcription
        self._buffers: dict[int, bytearray] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Begin listening — registers voice_recv callback and starts VAD loop."""
        self._running = True

        try:
            from discord_ext import voice_recv  # type: ignore[import]

            def on_voice_data(user: discord.User, data: voice_recv.VoiceData) -> None:
                uid = user.id if user else 0
                if uid not in self._buffers:
                    self._buffers[uid] = bytearray()
                self._buffers[uid].extend(data.pcm)

            self._vc.listen(on_voice_data)
        except ImportError:
            # voice_recv not installed; listening unavailable but don't crash
            pass

        self._task = asyncio.get_event_loop().create_task(self._vad_loop())

    async def _vad_loop(self) -> None:
        """Periodically run VAD over buffered audio and transcribe speech segments."""
        try:
            import numpy as np  # type: ignore[import]
            import torch  # type: ignore[import]

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            (get_speech_timestamps, *_) = utils
        except (ImportError, Exception):
            # silero-vad / torch not available — loop does nothing
            while self._running:
                await asyncio.sleep(0.5)
            return

        sample_rate = 16000
        min_bytes = sample_rate * 2  # 1 second of 16-bit mono audio

        while self._running:
            await asyncio.sleep(self._silence_duration_ms / 1000)

            for uid, buf in list(self._buffers.items()):
                if len(buf) < min_bytes:
                    continue

                raw = bytes(buf)
                self._buffers[uid] = bytearray()

                # Convert 16-bit stereo (discord default) to float32 mono
                audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if audio_np.ndim == 1 and len(audio_np) % 2 == 0:
                    audio_np = audio_np.reshape(-1, 2).mean(axis=1)
                audio_tensor = torch.from_numpy(audio_np)

                timestamps = get_speech_timestamps(
                    audio_tensor,
                    model,
                    threshold=self._vad_threshold,
                    sampling_rate=sample_rate,
                )

                if not timestamps:
                    continue

                # Extract speech bytes and feed to STT
                speech_audio = b"".join(
                    raw[ts["start"] * 2 : ts["end"] * 2] for ts in timestamps
                )

                async def _audio_gen(data: bytes = speech_audio):
                    yield data

                async for result in self._stt.transcribe(_audio_gen(), sample_rate=sample_rate):
                    result.user_id = str(uid)
                    self._on_transcription(str(uid), result)

    def stop(self) -> None:
        """Stop listening."""
        self._running = False
        try:
            self._vc.stop_listening()
        except Exception:
            pass
        if self._task is not None:
            self._task.cancel()
            self._task = None


class VoiceEngine:
    """Manages voice connections across guilds."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = {**DEFAULT_CONFIG, **(config or {})}
        self.connections: dict[int, discord.VoiceClient] = {}
        self._players: dict[int, AudioPlayer] = {}
        self._listeners: dict[int, AudioListener] = {}
        self._tts: TTSProvider | None = None
        self._stt: STTProvider | None = None
        self._event_handler: Callable[[dict[str, Any]], None] | None = None

    # ------------------------------------------------------------------ events

    def set_event_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        self._event_handler = handler

    def _emit(self, event: dict[str, Any]) -> None:
        if self._event_handler is not None:
            self._event_handler(event)

    # ------------------------------------------------------------------ config

    def update_config(self, updates: dict[str, Any]) -> None:
        """Merge partial config updates."""
        self.config.update(updates)

    # --------------------------------------------------------------- connections

    def get_connection(self, guild_id: int) -> discord.VoiceClient:
        """Return the VoiceClient for a guild, or raise VoiceError."""
        vc = self.connections.get(guild_id)
        if vc is None:
            raise VoiceError("Not connected")
        return vc

    async def connect(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        """Connect to a voice channel, or move if already in this guild."""
        guild_id = channel.guild.id
        if guild_id in self.connections:
            vc = self.connections[guild_id]
            await vc.move_to(channel)
        else:
            vc = await channel.connect()
            self.connections[guild_id] = vc

        player = AudioPlayer(vc, volume=self.config["playback_volume"])
        player.start()
        self._players[guild_id] = player

        self._emit({"event": "voice_connected", "guild_id": guild_id, "channel_id": channel.id})
        return vc

    async def disconnect(self, guild_id: int) -> None:
        """Disconnect from a guild's voice channel."""
        if guild_id in self._listeners:
            self._listeners.pop(guild_id).stop()

        if guild_id in self._players:
            await self._players.pop(guild_id).close()

        vc = self.connections.pop(guild_id, None)
        if vc is not None:
            await vc.disconnect()

        self._emit({"event": "voice_disconnected", "guild_id": guild_id})

    async def move(self, channel: discord.VoiceChannel) -> None:
        """Move to a different channel in the same guild."""
        guild_id = channel.guild.id
        vc = self.get_connection(guild_id)
        await vc.move_to(channel)
        self._emit({"event": "voice_connected", "guild_id": guild_id, "channel_id": channel.id})

    # ----------------------------------------------------------------- playback

    def _get_player(self, guild_id: int) -> AudioPlayer:
        player = self._players.get(guild_id)
        if player is None:
            raise VoiceError("Not connected")
        return player

    async def speak(
        self,
        guild_id: int,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> None:
        """Synthesize text with TTS and enqueue for playback."""
        if self._tts is None:
            self._tts = get_tts_provider(self.config["tts_provider"])

        tts_voice = voice or self.config.get("tts_voice", "default")
        chunks: list[bytes] = []
        async for chunk in await self._tts.synthesize(text, voice=tts_voice, speed=speed):
            chunks.append(chunk)
        pcm_data = b"".join(chunks)

        player = self._get_player(guild_id)
        await player.enqueue_pcm(pcm_data)
        self._emit({"event": "voice_playback_started", "guild_id": guild_id, "type": "tts"})

    async def play(self, guild_id: int, source: str) -> None:
        """Play a URL or file path."""
        player = self._get_player(guild_id)
        if source.startswith("http://") or source.startswith("https://"):
            await player.enqueue_url(source)
        else:
            await player.enqueue_file(source)
        self._emit({"event": "voice_playback_started", "guild_id": guild_id, "source": source})

    def stop(self, guild_id: int) -> None:
        self._get_player(guild_id).stop()

    def pause(self, guild_id: int) -> None:
        self._get_player(guild_id).pause()

    def resume(self, guild_id: int) -> None:
        self._get_player(guild_id).resume()

    # ---------------------------------------------------------------- listening

    async def listen_start(self, guild_id: int) -> None:
        """Start listening in a guild's voice channel."""
        if guild_id in self._listeners:
            return  # already listening

        if self._stt is None:
            self._stt = get_stt_provider(self.config["stt_provider"])

        vc = self.get_connection(guild_id)

        def on_transcription(user_id: str, result: TranscriptionResult) -> None:
            self._emit(
                {
                    "event": "voice_transcription",
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "text": result.text,
                    "confidence": result.confidence,
                    "is_final": result.is_final,
                }
            )

        listener = AudioListener(
            vc,
            self._stt,
            self.config["vad_threshold"],
            self.config["silence_duration_ms"],
            on_transcription,
        )
        listener.start()
        self._listeners[guild_id] = listener

    def listen_stop(self, guild_id: int) -> None:
        """Stop listening in a guild's voice channel."""
        listener = self._listeners.pop(guild_id, None)
        if listener is not None:
            listener.stop()

    # ------------------------------------------------------------------- status

    def status(self) -> list[dict[str, Any]]:
        """Return a list of connection status dicts."""
        result = []
        for guild_id, vc in self.connections.items():
            result.append(
                {
                    "guild_id": guild_id,
                    "channel_id": vc.channel.id if vc.channel else None,
                    "is_playing": vc.is_playing(),
                    "is_listening": guild_id in self._listeners,
                }
            )
        return result

    # -------------------------------------------------------------------- close

    async def close(self) -> None:
        """Disconnect all connections and clean up providers."""
        for guild_id in list(self.connections):
            await self.disconnect(guild_id)

        if self._tts is not None:
            await self._tts.close()
            self._tts = None

        if self._stt is not None:
            await self._stt.close()
            self._stt = None
