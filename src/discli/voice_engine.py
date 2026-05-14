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


def install_voice_recv_patches() -> bool:
    """Monkeypatch discord-ext-voice-recv to handle DAVE and survive bad packets.

    Idempotent — safe to call multiple times. Returns True if the patches are
    in place (either installed now or previously). Returns False only if
    voice_recv / davey aren't importable at all.

    Two patches are installed on ``PacketDecoder``:

    1. ``_decode_packet`` — calls ``davey.DaveSession.decrypt`` between the
       SecretBox layer and libopus. Without this, DAVE-encrypted audio (the
       default in modern Discord voice channels) decodes to garbage and
       libopus rejects every packet as "corrupted stream".
    2. ``pop_data`` — swallows ``OpusError`` so a single malformed packet
       can't unwind ``PacketRouter._do_run`` and tear the listening session
       down.
    """
    try:
        from discord.ext.voice_recv.opus import PacketDecoder  # type: ignore[import]
        from discord.opus import OpusError  # type: ignore[import]
        import davey  # type: ignore[import]
    except ImportError:
        return False

    if not getattr(PacketDecoder, "_discli_dave_patched", False):
        _orig_decode_packet = PacketDecoder._decode_packet

        def _dave_decode_packet(self, packet):
            if packet:
                try:
                    vc = self.sink.voice_client
                    conn = getattr(vc, "_connection", None)
                    dave = getattr(conn, "dave_session", None) if conn else None
                    user_id = vc._get_id_from_ssrc(self.ssrc) or self._cached_id
                    if dave is not None and user_id:
                        try:
                            decrypted = dave.decrypt(
                                user_id, davey.MediaType.audio, packet.decrypted_data
                            )
                        except Exception as exc:
                            if not getattr(self, "_discli_dave_logged", False):
                                print(
                                    f"[voice] DAVE decrypt raised on ssrc={self.ssrc}: "
                                    f"{exc!r} — falling back to raw bytes",
                                    flush=True,
                                )
                                self._discli_dave_logged = True
                        else:
                            if decrypted:
                                packet.decrypted_data = decrypted
                except Exception:
                    pass
            return _orig_decode_packet(self, packet)

        PacketDecoder._decode_packet = _dave_decode_packet  # type: ignore[assignment]
        PacketDecoder._discli_dave_patched = True  # type: ignore[attr-defined]

    if not getattr(PacketDecoder, "_discli_pop_patched", False):
        _orig_pop = PacketDecoder.pop_data

        def _safe_pop_data(self, *, timeout: float = 0):
            try:
                return _orig_pop(self, timeout=timeout)
            except OpusError as exc:
                print(
                    f"[voice] skipping bad opus packet on ssrc={self.ssrc}: {exc!r}",
                    flush=True,
                )
                return None

        PacketDecoder.pop_data = _safe_pop_data  # type: ignore[assignment]
        PacketDecoder._discli_pop_patched = True  # type: ignore[attr-defined]

    return True


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
        self._task = asyncio.get_running_loop().create_task(self._player_loop())

    async def _player_loop(self) -> None:
        """Pop sources from queue and play them sequentially."""
        loop = asyncio.get_running_loop()
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
                loop.call_soon_threadsafe(done_event.set)

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

    async def enqueue_pcm(
        self, pcm_data: bytes, *, sample_rate: int = 24000, channels: int = 1
    ) -> None:
        """Enqueue raw PCM bytes piped through FFmpeg.

        FFmpeg cannot auto-detect headerless PCM, so the input format must be
        declared explicitly. All supported TTS providers (OpenAI, ElevenLabs,
        Deepgram Aura) emit 24kHz mono signed 16-bit little-endian PCM; FFmpeg
        resamples that to the 48kHz stereo Discord expects.
        """
        buf = BytesIO(pcm_data)
        source = discord.FFmpegPCMAudio(
            buf,
            pipe=True,
            before_options=f"-f s16le -ar {sample_rate} -ac {channels}",
        )
        await self._queue.put(source)

    def stop(self) -> None:
        """Stop current playback. Does NOT stop listening on VoiceRecvClient."""
        if self._vc.is_playing():
            # VoiceRecvClient.stop() would kill listening too; prefer
            # stop_playing() when available.
            stop_playing = getattr(self._vc, "stop_playing", None)
            if callable(stop_playing):
                stop_playing()
            else:
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
    """Listens to voice channel audio and streams it to the STT provider.

    For meeting transcription (the primary use case) we open one long-lived
    streaming session per speaker and pump audio packets straight in — letting
    the STT service handle VAD/utterance segmentation server-side. No local
    silero/torch step.
    """

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
        # vad_threshold/silence_duration_ms retained for API compat — currently
        # unused since we delegate VAD to the streaming STT provider.
        self._vad_threshold = vad_threshold
        self._silence_duration_ms = silence_duration_ms
        self._on_transcription = on_transcription
        # uid -> asyncio.Queue feeding that speaker's STT session.
        self._queues: dict[int, asyncio.Queue] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False

    def start(self) -> None:
        """Begin listening via discord-ext-voice-recv."""
        self._running = True

        try:
            from discord.ext import voice_recv  # type: ignore[import]
        except ImportError:
            print(
                "[voice] discord-ext-voice-recv not installed — listening disabled",
                flush=True,
            )
            return

        if not hasattr(self._vc, "listen"):
            print(
                "[voice] voice client has no .listen() — connect must use "
                "voice_recv.VoiceRecvClient",
                flush=True,
            )
            return

        if not install_voice_recv_patches():
            print(
                "[voice] failed to install voice_recv patches — listening may fail",
                flush=True,
            )

        # `audioop` is in stdlib through 3.12 and provided by audioop-lts on 3.13+
        # (declared in the [voice] extra). Native C, ~100× faster than the
        # pure-Python loop this replaced.
        import audioop

        self._loop = asyncio.get_running_loop()
        loop = self._loop
        enqueue = self._enqueue
        packet_counts: dict[int, int] = {}

        # Subclass AudioSink directly. voice_recv.BasicSink(callback) hits an
        # upstream issue where the callback stops firing after the first packet
        # or two, which presents as "the bot can't hear anything".
        outer = self

        class _PCMSink(voice_recv.AudioSink):
            def __init__(self) -> None:
                super().__init__()

            def wants_opus(self) -> bool:
                return False

            def write(self, user, data) -> None:
                # PacketRouter.run() wraps this call in try/except/finally and
                # tears the reader down on ANY exception — swallow so one bad
                # packet can't kill the whole listening session.
                try:
                    if not outer._running:
                        return
                    uid = user.id if user else 0
                    # One-shot log per speaker confirms audio is flowing.
                    if uid not in packet_counts:
                        packet_counts[uid] = 0
                        print(f"[voice] receiving audio from uid={uid}", flush=True)
                    packet_counts[uid] += 1
                    # 48 kHz stereo s16le → mono s16le. Native C in audioop.
                    mono = audioop.tomono(data.pcm, 2, 0.5, 0.5)
                    loop.call_soon_threadsafe(enqueue, uid, mono)
                except Exception as exc:
                    print(
                        f"[voice] sink.write swallowed {type(exc).__name__}: {exc!r}",
                        flush=True,
                    )

            def cleanup(self) -> None:
                pass

        try:
            sink = _PCMSink()
            self._vc.listen(sink)
            members = []
            try:
                members = [
                    f"{m.id}:{m.display_name}" for m in self._vc.channel.members
                    if not m.bot
                ]
            except Exception:
                pass
            print(
                f"[voice] listening started guild={self._vc.guild.id} "
                f"channel={getattr(self._vc.channel, 'id', None)} "
                f"non_bot_members={members}",
                flush=True,
            )
        except Exception as exc:
            print(f"[voice] failed to start listening: {exc!r}", flush=True)
            return

    def _enqueue(self, uid: int, pcm: bytes) -> None:
        """Push a chunk of pcm onto the per-speaker queue, opening a new
        streaming STT session the first time we see this user."""
        if not self._running:
            return
        queue = self._queues.get(uid)
        if queue is None:
            queue = asyncio.Queue(maxsize=200)
            self._queues[uid] = queue
            assert self._loop is not None
            self._tasks[uid] = self._loop.create_task(
                self._run_user_session(uid, queue)
            )
            print(f"[voice] opened STT session for uid={uid}", flush=True)
        try:
            queue.put_nowait(pcm)
        except asyncio.QueueFull:
            # Drop oldest chunk under heavy load rather than blocking the loop.
            try:
                queue.get_nowait()
                queue.put_nowait(pcm)
            except Exception:
                pass

    async def _run_user_session(
        self, uid: int, queue: "asyncio.Queue[bytes | None]"
    ) -> None:
        """Drain ``queue`` into a streaming STT session for one speaker."""

        async def _audio_iter():
            while True:
                chunk = await queue.get()
                if chunk is None:
                    return
                yield chunk

        # Prefer the provider's streaming session if it has one (Deepgram does).
        stream_session = getattr(self._stt, "stream_session", None)
        try:
            if callable(stream_session):
                # We downmix to mono upstream; tell Deepgram mono.
                gen = stream_session(_audio_iter(), sample_rate=48000, channels=1)
            else:
                gen = self._stt.transcribe(_audio_iter(), sample_rate=48000)

            count = 0
            async for result in gen:
                count += 1
                tag = "FINAL" if result.is_final else "interim"
                print(
                    f"[voice] {tag} uid={uid} conf={result.confidence:.2f} "
                    f"text={result.text!r}",
                    flush=True,
                )
                try:
                    self._on_transcription(str(uid), result)
                except Exception as exc:
                    print(f"[voice] on_transcription error: {exc!r}", flush=True)
            print(f"[voice] STT session for uid={uid} closed (got {count} results)",
                  flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Deepgram's ApiError sometimes has empty repr — pull every
            # attribute we can find so the cause is visible.
            attrs = {
                k: getattr(exc, k, None)
                for k in ("status_code", "body", "headers", "message", "args")
            }
            print(
                f"[voice] STT session for uid={uid} crashed: "
                f"{type(exc).__name__} attrs={attrs}",
                flush=True,
            )

    def stop(self) -> None:
        """Stop listening — close all per-speaker STT sessions cleanly."""
        self._running = False
        # Pycord uses stop_recording; older voice_recv path used stop_listening.
        for method in ("stop_recording", "stop_listening"):
            fn = getattr(self._vc, method, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
                break
        # Signal each session to flush via a sentinel, then cancel the task.
        for queue in list(self._queues.values()):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        for task in list(self._tasks.values()):
            task.cancel()
        self._queues.clear()
        self._tasks.clear()


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
            # Prefer VoiceRecvClient so we can capture incoming audio.
            try:
                from discord.ext import voice_recv  # type: ignore[import]
                vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
                print(
                    f"[voice] connected ({type(vc).__name__}) "
                    f"to guild={guild_id} channel={channel.id}",
                    flush=True,
                )
            except ImportError:
                vc = await channel.connect()
                print(
                    "[voice] connected default VoiceClient — voice_recv missing",
                    flush=True,
                )
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
        # synthesize is an async generator; iterate it directly (do NOT await).
        async for chunk in self._tts.synthesize(text, voice=tts_voice, speed=speed):
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
            # Only surface finalized transcripts — interim partials cause
            # duplicate downstream handling (LLM replies per chunk, etc.).
            if not result.is_final:
                return
            vc = self.connections.get(guild_id)
            channel_id = str(vc.channel.id) if vc and vc.channel else None
            self._emit(
                {
                    "event": "voice_speech_detected",
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "text": result.text,
                    "confidence": result.confidence,
                    "is_final": True,
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
