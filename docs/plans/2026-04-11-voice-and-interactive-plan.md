# Voice & Interactive Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add full-duplex voice (TTS/STT), audio playback, and rich interactive components (modals, workflows, dashboards) to discli — both CLI commands and serve mode.

**Architecture:** Layered engines (`voice_engine.py`, `interact_engine.py`) that manage async state. CLI commands and serve.py both delegate to these engines. Provider protocols allow swapping TTS/STT backends.

**Tech Stack:** discord.py, discord-ext-voice-recv, silero-vad, PyNaCl, audioop-lts, ElevenLabs SDK, Deepgram SDK, Click

**Design doc:** `docs/plans/2026-04-11-voice-and-interactive-design.md`

---

### Task 1: Update Dependencies in pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add optional dependency groups**

In `pyproject.toml`, replace the existing `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
voice = [
    "PyNaCl>=1.5",
    "discord-ext-voice-recv>=0.5",
    "silero-vad>=5.0",
    "audioop-lts>=0.2; python_version>='3.13'",
]
elevenlabs = ["elevenlabs>=1.0"]
deepgram = ["deepgram-sdk>=3.0"]
openai-voice = ["openai>=1.0"]
local-voice = ["piper-tts>=1.2", "faster-whisper>=1.0"]
all-voice = [
    "discord-cli-agent[voice,elevenlabs,deepgram]",
]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
]
```

**Step 2: Verify install works**

Run: `pip install -e ".[dev]"`
Expected: installs cleanly (voice extras are optional)

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add voice and interactive optional dependency groups"
```

---

### Task 2: TTS Provider Protocol and ElevenLabs Implementation

**Files:**
- Create: `src/discli/tts.py`
- Create: `tests/test_tts.py`

**Step 1: Write the failing test**

Create `tests/test_tts.py`:

```python
import pytest
from discli.tts import get_tts_provider, TTSProvider, TTSError


def test_get_tts_provider_unknown_raises():
    with pytest.raises(TTSError, match="Unknown TTS provider"):
        get_tts_provider("nonexistent")


def test_tts_provider_protocol_has_required_methods():
    """TTSProvider protocol defines synthesize and close."""
    assert hasattr(TTSProvider, "synthesize")
    assert hasattr(TTSProvider, "close")


def test_get_tts_provider_elevenlabs_missing_key():
    """ElevenLabs provider raises if no API key."""
    import os
    old = os.environ.pop("ELEVENLABS_API_KEY", None)
    try:
        with pytest.raises(TTSError, match="ELEVENLABS_API_KEY"):
            get_tts_provider("elevenlabs")
    finally:
        if old:
            os.environ["ELEVENLABS_API_KEY"] = old
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'discli.tts'`

**Step 3: Write the TTS module**

Create `src/discli/tts.py`:

```python
"""TTS provider protocol and implementations."""

from __future__ import annotations

import os
from typing import AsyncIterator, Protocol, runtime_checkable


class TTSError(Exception):
    """Raised when TTS synthesis fails."""


@runtime_checkable
class TTSProvider(Protocol):
    """Protocol for text-to-speech providers."""

    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        """Yield PCM audio chunks (16-bit, 48kHz, stereo) from text."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...


class ElevenLabsTTS:
    """ElevenLabs TTS provider with streaming support."""

    def __init__(self, api_key: str, default_voice: str = "default"):
        try:
            from elevenlabs.client import AsyncElevenLabs
        except ImportError:
            raise TTSError(
                "elevenlabs package not installed. Run: pip install discord-cli-agent[elevenlabs]"
            )
        self._client = AsyncElevenLabs(api_key=api_key)
        self._default_voice = default_voice

    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        voice_id = voice if voice != "default" else self._default_voice
        try:
            response = await self._client.text_to_speech.convert_as_stream(
                text=text,
                voice_id=voice_id,
                output_format="pcm_24000",
            )
            async for chunk in response:
                yield chunk
        except Exception as e:
            raise TTSError(f"ElevenLabs synthesis failed: {e}") from e

    async def close(self) -> None:
        await self._client.close()


class OpenAITTS:
    """OpenAI TTS provider."""

    def __init__(self, api_key: str, default_voice: str = "alloy"):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise TTSError(
                "openai package not installed. Run: pip install discord-cli-agent[openai-voice]"
            )
        self._client = AsyncOpenAI(api_key=api_key)
        self._default_voice = default_voice

    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        voice_name = voice if voice != "default" else self._default_voice
        try:
            response = await self._client.audio.speech.create(
                model="tts-1",
                voice=voice_name,
                input=text,
                speed=speed,
                response_format="pcm",
            )
            async for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk
        except Exception as e:
            raise TTSError(f"OpenAI TTS failed: {e}") from e

    async def close(self) -> None:
        await self._client.close()


_PROVIDERS = {
    "elevenlabs": lambda: ElevenLabsTTS(
        api_key=_require_env("ELEVENLABS_API_KEY"),
    ),
    "openai": lambda: OpenAITTS(
        api_key=_require_env("OPENAI_API_KEY"),
    ),
}


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise TTSError(f"{name} environment variable is required")
    return val


def get_tts_provider(name: str) -> TTSProvider:
    """Get a TTS provider by name."""
    factory = _PROVIDERS.get(name)
    if not factory:
        raise TTSError(f"Unknown TTS provider: {name}. Available: {list(_PROVIDERS.keys())}")
    return factory()
```

**Step 4: Run tests**

Run: `pytest tests/test_tts.py -v`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add src/discli/tts.py tests/test_tts.py
git commit -m "feat: add TTS provider protocol with ElevenLabs and OpenAI implementations"
```

---

### Task 3: STT Provider Protocol and Deepgram Implementation

**Files:**
- Create: `src/discli/stt.py`
- Create: `tests/test_stt.py`

**Step 1: Write the failing test**

Create `tests/test_stt.py`:

```python
import pytest
from discli.stt import get_stt_provider, STTProvider, STTError, TranscriptionResult


def test_get_stt_provider_unknown_raises():
    with pytest.raises(STTError, match="Unknown STT provider"):
        get_stt_provider("nonexistent")


def test_stt_provider_protocol_has_required_methods():
    assert hasattr(STTProvider, "transcribe")
    assert hasattr(STTProvider, "close")


def test_transcription_result_fields():
    r = TranscriptionResult(text="hello", confidence=0.95, is_final=True, user_id="123")
    assert r.text == "hello"
    assert r.confidence == 0.95
    assert r.is_final is True
    assert r.user_id == "123"


def test_get_stt_provider_deepgram_missing_key():
    import os
    old = os.environ.pop("DEEPGRAM_API_KEY", None)
    try:
        with pytest.raises(STTError, match="DEEPGRAM_API_KEY"):
            get_stt_provider("deepgram")
    finally:
        if old:
            os.environ["DEEPGRAM_API_KEY"] = old
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stt.py -v`
Expected: FAIL

**Step 3: Write the STT module**

Create `src/discli/stt.py`:

```python
"""STT provider protocol and implementations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import AsyncIterator, Protocol, runtime_checkable


class STTError(Exception):
    """Raised when speech-to-text fails."""


@dataclass
class TranscriptionResult:
    """A transcription result from STT."""

    text: str
    confidence: float
    is_final: bool
    user_id: str | None = None


@runtime_checkable
class STTProvider(Protocol):
    """Protocol for speech-to-text providers."""

    async def transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 48000
    ) -> AsyncIterator[TranscriptionResult]:
        """Yield transcription results from an audio stream."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...


class DeepgramSTT:
    """Deepgram STT provider with real-time WebSocket streaming."""

    def __init__(self, api_key: str):
        try:
            from deepgram import DeepgramClient
        except ImportError:
            raise STTError(
                "deepgram-sdk not installed. Run: pip install discord-cli-agent[deepgram]"
            )
        self._client = DeepgramClient(api_key)

    async def transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 48000
    ) -> AsyncIterator[TranscriptionResult]:
        from deepgram import LiveTranscriptionEvents, LiveOptions

        options = LiveOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            encoding="linear16",
            sample_rate=sample_rate,
            channels=2,
            interim_results=True,
        )

        connection = self._client.listen.asyncwebsocket.v("1")
        results: list[TranscriptionResult] = []

        async def on_transcript(_, result, **kwargs):
            alt = result.channel.alternatives[0] if result.channel.alternatives else None
            if alt and alt.transcript.strip():
                results.append(
                    TranscriptionResult(
                        text=alt.transcript.strip(),
                        confidence=alt.confidence,
                        is_final=result.is_final,
                    )
                )

        connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        await connection.start(options)

        try:
            async for chunk in audio_stream:
                await connection.send(chunk)
                while results:
                    yield results.pop(0)
        finally:
            await connection.finish()

    async def close(self) -> None:
        pass


class OpenAISTT:
    """OpenAI Whisper STT provider (batch, not streaming)."""

    def __init__(self, api_key: str):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise STTError(
                "openai not installed. Run: pip install discord-cli-agent[openai-voice]"
            )
        self._client = AsyncOpenAI(api_key=api_key)

    async def transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 48000
    ) -> AsyncIterator[TranscriptionResult]:
        import io
        import wave

        # Collect all audio (Whisper is batch-only)
        audio_data = b""
        async for chunk in audio_stream:
            audio_data += chunk

        # Wrap in WAV container
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        buf.seek(0)
        buf.name = "audio.wav"

        result = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
        yield TranscriptionResult(
            text=result.text,
            confidence=1.0,
            is_final=True,
        )

    async def close(self) -> None:
        await self._client.close()


_PROVIDERS = {
    "deepgram": lambda: DeepgramSTT(api_key=_require_env("DEEPGRAM_API_KEY")),
    "openai": lambda: OpenAISTT(api_key=_require_env("OPENAI_API_KEY")),
}


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise STTError(f"{name} environment variable is required")
    return val


def get_stt_provider(name: str) -> STTProvider:
    """Get an STT provider by name."""
    factory = _PROVIDERS.get(name)
    if not factory:
        raise STTError(f"Unknown STT provider: {name}. Available: {list(_PROVIDERS.keys())}")
    return factory()
```

**Step 4: Run tests**

Run: `pytest tests/test_stt.py -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add src/discli/stt.py tests/test_stt.py
git commit -m "feat: add STT provider protocol with Deepgram and OpenAI Whisper implementations"
```

---

### Task 4: Voice Engine Core

**Files:**
- Create: `src/discli/voice_engine.py`
- Create: `tests/test_voice_engine.py`

**Step 1: Write the failing test**

Create `tests/test_voice_engine.py`:

```python
import pytest
from discli.voice_engine import VoiceEngine, VoiceError


def test_voice_engine_instantiates():
    engine = VoiceEngine()
    assert engine.connections == {}


def test_voice_engine_get_connection_not_connected():
    engine = VoiceEngine()
    with pytest.raises(VoiceError, match="Not connected"):
        engine.get_connection("123")


def test_voice_engine_config_defaults():
    engine = VoiceEngine()
    assert engine.config["tts_provider"] == "elevenlabs"
    assert engine.config["stt_provider"] == "deepgram"
    assert engine.config["vad_threshold"] == 0.5
    assert engine.config["silence_duration_ms"] == 800
    assert engine.config["playback_volume"] == 1.0


def test_voice_engine_update_config():
    engine = VoiceEngine()
    engine.update_config({"tts_provider": "openai", "vad_threshold": 0.7})
    assert engine.config["tts_provider"] == "openai"
    assert engine.config["vad_threshold"] == 0.7
    # Unchanged values stay
    assert engine.config["stt_provider"] == "deepgram"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_voice_engine.py -v`
Expected: FAIL

**Step 3: Write the voice engine**

Create `src/discli/voice_engine.py`:

```python
"""Voice engine — manages voice connections, audio playback, and listening."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import discord

from discli.tts import TTSProvider, get_tts_provider, TTSError
from discli.stt import STTProvider, get_stt_provider, STTError, TranscriptionResult


class VoiceError(Exception):
    """Raised when a voice operation fails."""


DEFAULT_CONFIG = {
    "tts_provider": "elevenlabs",
    "tts_voice": "default",
    "stt_provider": "deepgram",
    "vad_threshold": 0.5,
    "silence_duration_ms": 800,
    "playback_volume": 1.0,
}


class AudioPlayer:
    """Queue-based audio player for a voice connection."""

    def __init__(self, voice_client: discord.VoiceClient, volume: float = 1.0):
        self._vc = voice_client
        self._volume = volume
        self._queue: asyncio.Queue[discord.AudioSource | None] = asyncio.Queue()
        self._current: discord.AudioSource | None = None
        self._task: asyncio.Task | None = None
        self._playing = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self._player_loop())

    async def _player_loop(self) -> None:
        while True:
            source = await self._queue.get()
            if source is None:
                break
            self._current = source
            self._playing.set()
            volume_source = discord.PCMVolumeTransformer(source, volume=self._volume)
            done = asyncio.Event()
            self._vc.play(volume_source, after=lambda e: done.set())
            await done.wait()
            self._current = None
            self._playing.clear()

    async def enqueue(self, source: discord.AudioSource) -> None:
        await self._queue.put(source)

    async def enqueue_file(self, path: str) -> None:
        source = discord.FFmpegPCMAudio(path)
        await self.enqueue(source)

    async def enqueue_url(self, url: str) -> None:
        source = discord.FFmpegPCMAudio(url, before_options="-reconnect 1")
        await self.enqueue(source)

    async def enqueue_pcm(self, pcm_data: bytes, sample_rate: int = 48000) -> None:
        import io
        source = discord.FFmpegPCMAudio(
            io.BytesIO(pcm_data), pipe=True,
        )
        await self.enqueue(source)

    def stop(self) -> None:
        if self._vc.is_playing():
            self._vc.stop()

    def pause(self) -> None:
        if self._vc.is_playing():
            self._vc.pause()

    def resume(self) -> None:
        if self._vc.is_paused():
            self._vc.resume()

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(2.0, volume))

    @property
    def is_playing(self) -> bool:
        return self._vc.is_playing()

    async def close(self) -> None:
        await self._queue.put(None)
        if self._task:
            await self._task


class AudioListener:
    """Listens to voice channel audio, segments by VAD, feeds to STT."""

    def __init__(
        self,
        voice_client: discord.VoiceClient,
        stt: STTProvider,
        vad_threshold: float = 0.5,
        silence_duration_ms: int = 800,
        on_transcription: Callable[[TranscriptionResult], Any] | None = None,
    ):
        self._vc = voice_client
        self._stt = stt
        self._vad_threshold = vad_threshold
        self._silence_ms = silence_duration_ms
        self._on_transcription = on_transcription
        self._task: asyncio.Task | None = None
        self._running = False
        self._user_buffers: dict[int, bytearray] = {}

    async def start(self) -> None:
        """Start listening to the voice channel."""
        self._running = True

        try:
            from voice_recv import VoiceData
        except ImportError:
            raise VoiceError(
                "discord-ext-voice-recv not installed. "
                "Run: pip install discord-cli-agent[voice]"
            )

        def callback(user, data: VoiceData):
            if user is None:
                return
            uid = user.id
            if uid not in self._user_buffers:
                self._user_buffers[uid] = bytearray()
            self._user_buffers[uid].extend(data.pcm)

        self._vc.listen(callback)
        self._task = asyncio.create_task(self._vad_loop())

    async def _vad_loop(self) -> None:
        """Periodically check buffers, run VAD, and send to STT."""
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad", model="silero_vad"
            )
            (get_speech_timestamps, _, _, _, _) = utils
        except ImportError:
            raise VoiceError("silero-vad not installed. Run: pip install discord-cli-agent[voice]")

        while self._running:
            await asyncio.sleep(self._silence_ms / 1000.0)

            for uid, buf in list(self._user_buffers.items()):
                if len(buf) < 9600:  # Less than 100ms of audio at 48kHz stereo 16-bit
                    continue

                audio_bytes = bytes(buf)
                self._user_buffers[uid] = bytearray()

                # Run VAD in thread to avoid blocking
                import numpy as np
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                # Convert stereo to mono for VAD
                if len(audio_np) % 2 == 0:
                    audio_np = audio_np.reshape(-1, 2).mean(axis=1)

                import torch
                tensor = torch.from_numpy(audio_np)
                speech_timestamps = get_speech_timestamps(
                    tensor, model, threshold=self._vad_threshold, sampling_rate=16000
                )

                if speech_timestamps:
                    # Speech detected — send to STT
                    async def audio_gen():
                        yield audio_bytes

                    async for result in self._stt.transcribe(audio_gen()):
                        result.user_id = str(uid)
                        if self._on_transcription:
                            self._on_transcription(result)

    async def stop(self) -> None:
        self._running = False
        self._vc.stop_listening()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class VoiceEngine:
    """Manages voice connections across guilds."""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.connections: dict[str, discord.VoiceClient] = {}  # guild_id -> VoiceClient
        self._players: dict[str, AudioPlayer] = {}  # guild_id -> AudioPlayer
        self._listeners: dict[str, AudioListener] = {}  # guild_id -> AudioListener
        self._tts: TTSProvider | None = None
        self._stt: STTProvider | None = None
        self._on_event: Callable[[dict], Any] | None = None

    def set_event_handler(self, handler: Callable[[dict], Any]) -> None:
        self._on_event = handler

    def _emit(self, event: dict) -> None:
        if self._on_event:
            self._on_event(event)

    def update_config(self, updates: dict) -> None:
        self.config.update(updates)

    def get_connection(self, guild_id: str) -> discord.VoiceClient:
        vc = self.connections.get(guild_id)
        if not vc:
            raise VoiceError(f"Not connected to voice in guild {guild_id}")
        return vc

    async def connect(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        guild_id = str(channel.guild.id)
        if guild_id in self.connections:
            vc = self.connections[guild_id]
            if vc.is_connected():
                await vc.move_to(channel)
                self._emit({"event": "voice_connected", "guild_id": guild_id, "channel_id": str(channel.id)})
                return vc

        vc = await channel.connect()
        self.connections[guild_id] = vc

        player = AudioPlayer(vc, volume=self.config["playback_volume"])
        player.start()
        self._players[guild_id] = player

        self._emit({"event": "voice_connected", "guild_id": guild_id, "channel_id": str(channel.id)})
        return vc

    async def disconnect(self, guild_id: str) -> None:
        vc = self.connections.pop(guild_id, None)
        if not vc:
            raise VoiceError(f"Not connected to voice in guild {guild_id}")

        if guild_id in self._listeners:
            await self._listeners[guild_id].stop()
            del self._listeners[guild_id]

        if guild_id in self._players:
            await self._players[guild_id].close()
            del self._players[guild_id]

        await vc.disconnect()
        self._emit({"event": "voice_disconnected", "guild_id": guild_id})

    async def move(self, channel: discord.VoiceChannel) -> None:
        guild_id = str(channel.guild.id)
        vc = self.get_connection(guild_id)
        await vc.move_to(channel)
        self._emit({"event": "voice_connected", "guild_id": guild_id, "channel_id": str(channel.id)})

    async def speak(self, guild_id: str, text: str, *, voice: str = "default", speed: float = 1.0) -> None:
        self.get_connection(guild_id)  # Verify connected
        player = self._players[guild_id]

        if not self._tts:
            self._tts = get_tts_provider(self.config["tts_provider"])

        pcm_chunks = []
        async for chunk in self._tts.synthesize(text, voice=voice, speed=speed):
            pcm_chunks.append(chunk)

        pcm_data = b"".join(pcm_chunks)
        self._emit({"event": "voice_playback_started", "guild_id": guild_id, "source": "tts"})
        await player.enqueue_pcm(pcm_data)

    async def play(self, guild_id: str, source: str) -> None:
        self.get_connection(guild_id)
        player = self._players[guild_id]
        self._emit({"event": "voice_playback_started", "guild_id": guild_id, "source": source})

        if source.startswith(("http://", "https://")):
            await player.enqueue_url(source)
        else:
            await player.enqueue_file(source)

    def stop(self, guild_id: str) -> None:
        player = self._players.get(guild_id)
        if player:
            player.stop()

    def pause(self, guild_id: str) -> None:
        player = self._players.get(guild_id)
        if player:
            player.pause()

    def resume(self, guild_id: str) -> None:
        player = self._players.get(guild_id)
        if player:
            player.resume()

    async def listen_start(self, guild_id: str) -> None:
        vc = self.get_connection(guild_id)

        if not self._stt:
            self._stt = get_stt_provider(self.config["stt_provider"])

        def on_transcription(result: TranscriptionResult):
            self._emit({
                "event": "voice_transcription",
                "guild_id": guild_id,
                "user_id": result.user_id,
                "text": result.text,
                "confidence": result.confidence,
                "is_final": result.is_final,
            })

        listener = AudioListener(
            vc, self._stt,
            vad_threshold=self.config["vad_threshold"],
            silence_duration_ms=self.config["silence_duration_ms"],
            on_transcription=on_transcription,
        )
        await listener.start()
        self._listeners[guild_id] = listener

    async def listen_stop(self, guild_id: str) -> None:
        listener = self._listeners.pop(guild_id, None)
        if listener:
            await listener.stop()

    def status(self) -> list[dict]:
        result = []
        for gid, vc in self.connections.items():
            result.append({
                "guild_id": gid,
                "channel_id": str(vc.channel.id) if vc.channel else None,
                "connected": vc.is_connected(),
                "playing": self._players.get(gid, None) is not None and self._players[gid].is_playing,
                "listening": gid in self._listeners,
            })
        return result

    async def close(self) -> None:
        for gid in list(self.connections.keys()):
            try:
                await self.disconnect(gid)
            except Exception:
                pass
        if self._tts:
            await self._tts.close()
        if self._stt:
            await self._stt.close()
```

**Step 4: Run tests**

Run: `pytest tests/test_voice_engine.py -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add src/discli/voice_engine.py tests/test_voice_engine.py
git commit -m "feat: add VoiceEngine with AudioPlayer, AudioListener, and connection management"
```

---

### Task 5: Interactive Engine — Interaction Router, Workflows, and Dashboards

**Files:**
- Create: `src/discli/interact_engine.py`
- Create: `tests/test_interact_engine.py`

**Step 1: Write the failing test**

Create `tests/test_interact_engine.py`:

```python
import pytest
from discli.interact_engine import (
    InteractEngine,
    InteractError,
    WorkflowDefinition,
    WorkflowStep,
    DashboardDefinition,
    DashboardPage,
)


def test_interact_engine_instantiates():
    engine = InteractEngine()
    assert engine.workflows == {}
    assert engine.dashboards == {}


def test_workflow_definition():
    steps = [
        WorkflowStep(
            step_id="intro",
            step_type="message",
            content="Welcome!",
            components=[{"type": "button", "label": "Next", "custom_id": "next"}],
        ),
        WorkflowStep(
            step_id="name",
            step_type="modal",
            content="Enter your name",
            fields=[{"label": "Name", "style": "short", "required": True}],
        ),
    ]
    wf = WorkflowDefinition(workflow_id="onboard", steps=steps)
    assert wf.workflow_id == "onboard"
    assert len(wf.steps) == 2
    assert wf.steps[0].step_type == "message"


def test_dashboard_definition():
    pages = [
        DashboardPage(
            embed={"title": "Page 1", "description": "First page"},
        ),
        DashboardPage(
            embed={"title": "Page 2", "description": "Second page"},
        ),
    ]
    dash = DashboardDefinition(dashboard_id="stats", pages=pages, refresh_interval=60)
    assert dash.dashboard_id == "stats"
    assert len(dash.pages) == 2
    assert dash.refresh_interval == 60


def test_interaction_router_prefix_routing():
    engine = InteractEngine()
    assert engine.route_custom_id("modal:signup") == "modal"
    assert engine.route_custom_id("wf:step1:next") == "workflow"
    assert engine.route_custom_id("dash:stats:page") == "dashboard"
    assert engine.route_custom_id("unknown:thing") is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interact_engine.py -v`
Expected: FAIL

**Step 3: Write the interact engine**

Create `src/discli/interact_engine.py`:

```python
"""Interactive engine — modals, workflows, and dashboards."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import discord


class InteractError(Exception):
    """Raised when an interactive operation fails."""


# ── Data Models ──────────────────────────────────────────────────────


@dataclass
class WorkflowStep:
    step_id: str
    step_type: str  # "message", "select", "modal", "confirm"
    content: str = ""
    components: list[dict] = field(default_factory=list)
    fields: list[dict] = field(default_factory=list)  # For modal steps
    next: dict[str, str] | str | None = None  # Conditional or direct next step
    timeout: int = 300  # seconds


@dataclass
class WorkflowDefinition:
    workflow_id: str
    steps: list[WorkflowStep]

    def get_step(self, step_id: str) -> WorkflowStep | None:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None


@dataclass
class WorkflowState:
    workflow_id: str
    user_id: str
    channel_id: str
    current_step: str
    collected_data: dict = field(default_factory=dict)
    message_id: str | None = None


@dataclass
class DashboardPage:
    embed: dict = field(default_factory=dict)
    components: list[dict] = field(default_factory=list)


@dataclass
class DashboardDefinition:
    dashboard_id: str
    pages: list[DashboardPage]
    refresh_interval: int = 0  # 0 = no auto-refresh
    components: list[dict] = field(default_factory=list)  # Global components (e.g., pagination)


@dataclass
class DashboardState:
    dashboard_id: str
    channel_id: str
    message_id: str | None = None
    current_page: int = 0
    data: dict = field(default_factory=dict)  # Dynamic data for updates


# ── Interaction Router ───────────────────────────────────────────────

_PREFIX_MAP = {
    "modal:": "modal",
    "wf:": "workflow",
    "dash:": "dashboard",
    "voice:": "voice",
}


# ── Engine ───────────────────────────────────────────────────────────


class InteractEngine:
    """Manages interactive Discord components: modals, workflows, dashboards."""

    def __init__(self):
        self.workflows: dict[str, WorkflowState] = {}  # (user_id:workflow_id) -> state
        self.dashboards: dict[str, DashboardState] = {}  # dashboard_id -> state
        self._workflow_defs: dict[str, WorkflowDefinition] = {}
        self._dashboard_defs: dict[str, DashboardDefinition] = {}
        self._timeout_tasks: dict[str, asyncio.Task] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}
        self._on_event: Callable[[dict], Any] | None = None

    def set_event_handler(self, handler: Callable[[dict], Any]) -> None:
        self._on_event = handler

    def _emit(self, event: dict) -> None:
        if self._on_event:
            self._on_event(event)

    @staticmethod
    def route_custom_id(custom_id: str) -> str | None:
        """Route a custom_id to its handler type based on prefix."""
        for prefix, handler_type in _PREFIX_MAP.items():
            if custom_id.startswith(prefix):
                return handler_type
        return None

    # ── Modals ───────────────────────────────────────────────────────

    @staticmethod
    def build_modal(
        title: str,
        custom_id: str,
        fields: list[dict],
    ) -> discord.ui.Modal:
        """Build a Discord modal from a field spec.

        Each field dict: {label, style ("short"|"paragraph"), required, placeholder, default, max_length}
        """
        modal = discord.ui.Modal(title=title, custom_id=f"modal:{custom_id}")

        for f in fields:
            style = discord.TextStyle.short if f.get("style") == "short" else discord.TextStyle.paragraph
            item = discord.ui.TextInput(
                label=f["label"],
                style=style,
                required=f.get("required", False),
                placeholder=f.get("placeholder", ""),
                default=f.get("default", ""),
                max_length=f.get("max_length", 4000),
                custom_id=f.get("custom_id", f["label"].lower().replace(" ", "_")),
            )
            modal.add_item(item)

        return modal

    # ── Workflows ────────────────────────────────────────────────────

    async def workflow_start(
        self,
        channel: discord.TextChannel,
        user_id: str,
        definition: WorkflowDefinition,
    ) -> str:
        """Start a workflow for a user. Returns workflow key."""
        key = f"{user_id}:{definition.workflow_id}"
        self._workflow_defs[definition.workflow_id] = definition

        state = WorkflowState(
            workflow_id=definition.workflow_id,
            user_id=user_id,
            channel_id=str(channel.id),
            current_step=definition.steps[0].step_id,
        )
        self.workflows[key] = state

        await self._send_workflow_step(channel, state, definition.steps[0])
        self._start_timeout(key, definition.steps[0].timeout)

        return key

    async def _send_workflow_step(
        self,
        channel: discord.TextChannel,
        state: WorkflowState,
        step: WorkflowStep,
    ) -> None:
        """Send the current workflow step to the channel."""
        if step.step_type in ("message", "confirm", "select"):
            view = discord.ui.View(timeout=step.timeout)

            if step.step_type == "confirm":
                # Add Yes/No buttons
                yes_btn = discord.ui.Button(
                    label="Yes", style=discord.ButtonStyle.success,
                    custom_id=f"wf:{state.workflow_id}:{step.step_id}:yes",
                )
                no_btn = discord.ui.Button(
                    label="No", style=discord.ButtonStyle.danger,
                    custom_id=f"wf:{state.workflow_id}:{step.step_id}:no",
                )
                view.add_item(yes_btn)
                view.add_item(no_btn)
            elif step.step_type == "select":
                select = discord.ui.Select(
                    custom_id=f"wf:{state.workflow_id}:{step.step_id}:select",
                    options=[
                        discord.SelectOption(label=c["label"], value=c.get("value", c["label"]))
                        for c in step.components
                    ],
                )
                view.add_item(select)
            else:
                # Generic buttons from components
                for comp in step.components:
                    btn = discord.ui.Button(
                        label=comp["label"],
                        style=discord.ButtonStyle.primary,
                        custom_id=f"wf:{state.workflow_id}:{step.step_id}:{comp['custom_id']}",
                    )
                    view.add_item(btn)

            msg = await channel.send(content=step.content, view=view)
            state.message_id = str(msg.id)

        # Modal steps are triggered by a button in a prior step — handled in handle_workflow_interaction

    def _start_timeout(self, key: str, timeout: int) -> None:
        if key in self._timeout_tasks:
            self._timeout_tasks[key].cancel()

        async def _timeout():
            await asyncio.sleep(timeout)
            state = self.workflows.pop(key, None)
            if state:
                self._emit({
                    "event": "workflow_timeout",
                    "workflow_id": state.workflow_id,
                    "user_id": state.user_id,
                    "step_id": state.current_step,
                })

        self._timeout_tasks[key] = asyncio.create_task(_timeout())

    async def handle_workflow_interaction(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        """Handle a workflow-related interaction."""
        # Parse: wf:{workflow_id}:{step_id}:{action}
        parts = custom_id.split(":")
        if len(parts) < 4:
            return

        _, wf_id, step_id, action = parts[0], parts[1], parts[2], parts[3]
        user_id = str(interaction.user.id)
        key = f"{user_id}:{wf_id}"

        state = self.workflows.get(key)
        if not state or state.current_step != step_id:
            await interaction.response.send_message("This workflow has expired.", ephemeral=True)
            return

        wf_def = self._workflow_defs.get(wf_id)
        if not wf_def:
            return

        step = wf_def.get_step(step_id)
        if not step:
            return

        # Record input
        state.collected_data[step_id] = action

        self._emit({
            "event": "workflow_step_completed",
            "workflow_id": wf_id,
            "step_id": step_id,
            "user_id": user_id,
            "user_input": action,
        })

        # Determine next step
        next_step_id = None
        if isinstance(step.next, dict):
            next_step_id = step.next.get(action)
        elif isinstance(step.next, str):
            next_step_id = step.next

        if next_step_id:
            next_step = wf_def.get_step(next_step_id)
            if next_step:
                state.current_step = next_step_id
                channel = interaction.channel
                if next_step.step_type == "modal":
                    modal = self.build_modal(
                        title=next_step.content,
                        custom_id=f"wf_modal:{wf_id}:{next_step_id}",
                        fields=next_step.fields,
                    )
                    await interaction.response.send_modal(modal)
                else:
                    await interaction.response.defer()
                    await self._send_workflow_step(channel, state, next_step)
                self._start_timeout(key, next_step.timeout)
                return

        # No next step — workflow complete
        self.workflows.pop(key, None)
        if key in self._timeout_tasks:
            self._timeout_tasks[key].cancel()
            del self._timeout_tasks[key]

        await interaction.response.send_message("Workflow complete!", ephemeral=True)
        self._emit({
            "event": "workflow_finished",
            "workflow_id": wf_id,
            "user_id": user_id,
            "collected_data": state.collected_data,
        })

    def workflow_cancel(self, user_id: str, workflow_id: str) -> bool:
        key = f"{user_id}:{workflow_id}"
        state = self.workflows.pop(key, None)
        if key in self._timeout_tasks:
            self._timeout_tasks[key].cancel()
            del self._timeout_tasks[key]
        return state is not None

    # ── Dashboards ───────────────────────────────────────────────────

    async def dashboard_create(
        self,
        channel: discord.TextChannel,
        definition: DashboardDefinition,
    ) -> str:
        """Create a persistent dashboard message. Returns dashboard_id."""
        self._dashboard_defs[definition.dashboard_id] = definition

        state = DashboardState(
            dashboard_id=definition.dashboard_id,
            channel_id=str(channel.id),
        )

        msg = await self._render_dashboard(channel, definition, state)
        state.message_id = str(msg.id)
        self.dashboards[definition.dashboard_id] = state

        if definition.refresh_interval > 0:
            self._start_refresh(definition.dashboard_id, definition.refresh_interval, channel)

        return definition.dashboard_id

    async def _render_dashboard(
        self,
        channel: discord.TextChannel,
        definition: DashboardDefinition,
        state: DashboardState,
    ) -> discord.Message:
        """Render the current dashboard page."""
        page = definition.pages[state.current_page]

        embed = discord.Embed(
            title=page.embed.get("title", ""),
            description=page.embed.get("description", ""),
        )
        if "color" in page.embed:
            embed.color = discord.Color(int(str(page.embed["color"]).lstrip("#"), 16))
        for f in page.embed.get("fields", []):
            embed.add_field(name=f["name"], value=f["value"], inline=f.get("inline", True))

        view = discord.ui.View(timeout=None)

        # Pagination buttons
        if len(definition.pages) > 1:
            prev_btn = discord.ui.Button(
                label="Previous", style=discord.ButtonStyle.secondary,
                custom_id=f"dash:{definition.dashboard_id}:prev",
                disabled=state.current_page == 0,
            )
            next_btn = discord.ui.Button(
                label="Next", style=discord.ButtonStyle.secondary,
                custom_id=f"dash:{definition.dashboard_id}:next",
                disabled=state.current_page >= len(definition.pages) - 1,
            )
            page_label = discord.ui.Button(
                label=f"{state.current_page + 1}/{len(definition.pages)}",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"dash:{definition.dashboard_id}:page_label",
            )
            view.add_item(prev_btn)
            view.add_item(page_label)
            view.add_item(next_btn)

        # Custom components from page
        for comp in page.components:
            if comp.get("type") == "button":
                btn = discord.ui.Button(
                    label=comp["label"],
                    style=getattr(discord.ButtonStyle, comp.get("style", "primary")),
                    custom_id=f"dash:{definition.dashboard_id}:{comp['custom_id']}",
                )
                view.add_item(btn)

        if state.message_id:
            try:
                msg = await channel.fetch_message(int(state.message_id))
                await msg.edit(embed=embed, view=view)
                return msg
            except discord.NotFound:
                pass

        return await channel.send(embed=embed, view=view)

    def _start_refresh(self, dashboard_id: str, interval: int, channel: discord.TextChannel) -> None:
        async def _refresh_loop():
            while dashboard_id in self.dashboards:
                await asyncio.sleep(interval)
                state = self.dashboards.get(dashboard_id)
                definition = self._dashboard_defs.get(dashboard_id)
                if state and definition:
                    await self._render_dashboard(channel, definition, state)

        self._refresh_tasks[dashboard_id] = asyncio.create_task(_refresh_loop())

    async def handle_dashboard_interaction(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        """Handle a dashboard-related interaction."""
        parts = custom_id.split(":")
        if len(parts) < 3:
            return

        _, dash_id, action = parts[0], parts[1], parts[2]

        state = self.dashboards.get(dash_id)
        definition = self._dashboard_defs.get(dash_id)
        if not state or not definition:
            await interaction.response.send_message("Dashboard not found.", ephemeral=True)
            return

        if action == "prev" and state.current_page > 0:
            state.current_page -= 1
        elif action == "next" and state.current_page < len(definition.pages) - 1:
            state.current_page += 1
        else:
            # Custom component interaction
            self._emit({
                "event": "dashboard_interaction",
                "dashboard_id": dash_id,
                "user_id": str(interaction.user.id),
                "component_id": action,
            })
            await interaction.response.defer()
            return

        await interaction.response.defer()
        await self._render_dashboard(interaction.channel, definition, state)

    async def dashboard_update(self, dashboard_id: str, updates: dict, channel: discord.TextChannel) -> None:
        """Update a dashboard's data and re-render."""
        state = self.dashboards.get(dashboard_id)
        definition = self._dashboard_defs.get(dashboard_id)
        if not state or not definition:
            raise InteractError(f"Dashboard {dashboard_id} not found")

        state.data.update(updates)

        # Update page content from updates if provided
        if "pages" in updates:
            for i, page_update in enumerate(updates["pages"]):
                if i < len(definition.pages):
                    if "embed" in page_update:
                        definition.pages[i].embed.update(page_update["embed"])

        await self._render_dashboard(channel, definition, state)

    async def dashboard_delete(self, dashboard_id: str, channel: discord.TextChannel) -> None:
        """Delete a dashboard."""
        state = self.dashboards.pop(dashboard_id, None)
        self._dashboard_defs.pop(dashboard_id, None)

        if dashboard_id in self._refresh_tasks:
            self._refresh_tasks[dashboard_id].cancel()
            del self._refresh_tasks[dashboard_id]

        if state and state.message_id:
            try:
                msg = await channel.fetch_message(int(state.message_id))
                await msg.delete()
            except discord.NotFound:
                pass

    async def close(self) -> None:
        for task in self._timeout_tasks.values():
            task.cancel()
        for task in self._refresh_tasks.values():
            task.cancel()
        self._timeout_tasks.clear()
        self._refresh_tasks.clear()
        self.workflows.clear()
        self.dashboards.clear()
```

**Step 4: Run tests**

Run: `pytest tests/test_interact_engine.py -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add src/discli/interact_engine.py tests/test_interact_engine.py
git commit -m "feat: add InteractEngine with workflows, dashboards, and interaction routing"
```

---

### Task 6: Voice CLI Commands

**Files:**
- Create: `src/discli/commands/voice.py`
- Modify: `src/discli/cli.py` (register voice group)

**Step 1: Write the voice command module**

Create `src/discli/commands/voice.py`:

```python
"""Voice commands — join, leave, speak, play, listen, converse."""

import asyncio

import click
import discord

from discli.client import run_discord
from discli.utils import output


@click.group("voice")
def voice_group():
    """Voice channel operations — join, speak, play, listen."""


@voice_group.command("join")
@click.argument("channel")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_join(ctx, channel, server):
    """Join a voice channel."""
    from discli.utils import resolve_channel, resolve_guild

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            if server:
                guild = resolve_guild(client, server)
                ch = discord.utils.get(guild.voice_channels, name=channel)
                if not ch:
                    try:
                        ch = guild.get_channel(int(channel))
                    except ValueError:
                        pass
                if not ch or not isinstance(ch, discord.VoiceChannel):
                    raise click.ClickException(f"Voice channel '{channel}' not found in {guild.name}")
            else:
                ch = None
                for g in client.guilds:
                    ch = discord.utils.get(g.voice_channels, name=channel)
                    if ch:
                        break
                    try:
                        ch = g.get_channel(int(channel))
                        if ch and isinstance(ch, discord.VoiceChannel):
                            break
                        ch = None
                    except ValueError:
                        continue
                if not ch:
                    raise click.ClickException(f"Voice channel '{channel}' not found")

            engine = VoiceEngine()
            await engine.connect(ch)
            data = {"channel_id": str(ch.id), "channel": ch.name, "guild": ch.guild.name}
            output(ctx, data, plain_text=f"Joined voice channel: {ch.name} ({ch.guild.name})")
            await engine.close()

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("leave")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_leave(ctx, server):
    """Leave voice channel in a server."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine

            guild = None
            if server:
                from discli.utils import resolve_guild
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild:
                raise click.ClickException("Not connected to any voice channel")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client
            await engine.disconnect(str(guild.id))
            output(ctx, {"ok": True}, plain_text=f"Left voice in {guild.name}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("speak")
@click.argument("text")
@click.option("--server", default=None, help="Server name or ID.")
@click.option("--voice", default="default", help="TTS voice name/ID.")
@click.option("--speed", default=1.0, help="Speech speed multiplier.")
@click.pass_context
def voice_speak(ctx, text, server, voice, speed):
    """Speak text in the current voice channel via TTS."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine
            from discli.utils import resolve_guild

            guild = None
            if server:
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild or not guild.voice_client:
                raise click.ClickException("Not connected to any voice channel. Run 'discli voice join' first.")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client
            await engine.speak(str(guild.id), text, voice=voice, speed=speed)
            output(ctx, {"ok": True, "text": text}, plain_text=f"Spoke: {text}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("play")
@click.argument("source")
@click.option("--server", default=None, help="Server name or ID.")
@click.option("--volume", default=1.0, help="Playback volume (0.0-2.0).")
@click.pass_context
def voice_play(ctx, source, server, volume):
    """Play audio from a file path or URL."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine
            from discli.utils import resolve_guild

            guild = None
            if server:
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild or not guild.voice_client:
                raise click.ClickException("Not connected to any voice channel.")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client
            await engine.play(str(guild.id), source)
            output(ctx, {"ok": True, "source": source}, plain_text=f"Playing: {source}")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("stop")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_stop(ctx, server):
    """Stop current playback."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine
            from discli.utils import resolve_guild

            guild = None
            if server:
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild or not guild.voice_client:
                raise click.ClickException("Not connected to any voice channel.")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client
            engine.stop(str(guild.id))
            output(ctx, {"ok": True}, plain_text="Playback stopped")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("pause")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_pause(ctx, server):
    """Pause current playback."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine
            from discli.utils import resolve_guild

            guild = None
            if server:
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild or not guild.voice_client:
                raise click.ClickException("Not connected to any voice channel.")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client
            engine.pause(str(guild.id))
            output(ctx, {"ok": True}, plain_text="Playback paused")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("resume")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def voice_resume(ctx, server):
    """Resume paused playback."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine
            from discli.utils import resolve_guild

            guild = None
            if server:
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild or not guild.voice_client:
                raise click.ClickException("Not connected to any voice channel.")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client
            engine.resume(str(guild.id))
            output(ctx, {"ok": True}, plain_text="Playback resumed")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("listen")
@click.option("--server", default=None, help="Server name or ID.")
@click.option("--duration", default=0, help="Listen duration in seconds (0=until Ctrl+C).")
@click.option("--continuous", is_flag=True, help="Print transcriptions continuously.")
@click.pass_context
def voice_listen(ctx, server, duration, continuous):
    """Listen to a voice channel and print transcriptions."""

    def action(client):
        async def _action(client):
            from discli.voice_engine import VoiceEngine
            from discli.utils import resolve_guild

            guild = None
            if server:
                guild = resolve_guild(client, server)
            else:
                for g in client.guilds:
                    if g.voice_client:
                        guild = g
                        break
            if not guild or not guild.voice_client:
                raise click.ClickException("Not connected to any voice channel.")

            engine = VoiceEngine()
            engine.connections[str(guild.id)] = guild.voice_client

            def on_transcription(event):
                text = event.get("text", "")
                user = event.get("user_id", "unknown")
                click.echo(f"[{user}] {text}")

            engine.set_event_handler(on_transcription)
            await engine.listen_start(str(guild.id))

            try:
                if duration > 0:
                    await asyncio.sleep(duration)
                else:
                    # Run until cancelled
                    while True:
                        await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await engine.listen_stop(str(guild.id))
                output(ctx, {"ok": True}, plain_text="Stopped listening")

        return _action(client)

    run_discord(ctx, action)


@voice_group.command("status")
@click.pass_context
def voice_status(ctx):
    """Show active voice connections."""

    def action(client):
        async def _action(client):
            connections = []
            for g in client.guilds:
                if g.voice_client and g.voice_client.is_connected():
                    connections.append({
                        "guild": g.name,
                        "guild_id": str(g.id),
                        "channel": g.voice_client.channel.name if g.voice_client.channel else None,
                        "channel_id": str(g.voice_client.channel.id) if g.voice_client.channel else None,
                        "playing": g.voice_client.is_playing(),
                    })
            if connections:
                plain = "\n".join(
                    f"{c['guild']}: #{c['channel']} (playing: {c['playing']})"
                    for c in connections
                )
            else:
                plain = "No active voice connections."
            output(ctx, connections, plain_text=plain)

        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register voice group in cli.py**

Add import and registration to `src/discli/cli.py`:

```python
# Add after existing imports:
from discli.commands.voice import voice_group

# Add after existing main.add_command() calls:
main.add_command(voice_group)
```

**Step 3: Run existing tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: all existing tests PASS

**Step 4: Commit**

```bash
git add src/discli/commands/voice.py src/discli/cli.py
git commit -m "feat: add voice CLI commands (join, leave, speak, play, stop, pause, resume, listen, status)"
```

---

### Task 7: Interactive CLI Commands

**Files:**
- Create: `src/discli/commands/interact.py`
- Modify: `src/discli/cli.py` (register interact group)

**Step 1: Write the interact command module**

Create `src/discli/commands/interact.py`:

```python
"""Interactive commands — modals, workflows, dashboards."""

import json

import click
import discord

from discli.client import run_discord
from discli.utils import output


@click.group("interact")
def interact_group():
    """Interactive components — modals, workflows, dashboards."""


@interact_group.command("modal")
@click.argument("title")
@click.option("--field", "-f", multiple=True, help="Field spec: 'Label:style:required' (style=short|paragraph)")
@click.option("--channel", required=True, help="Channel to send trigger message.")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def interact_modal(ctx, title, field, channel, server):
    """Send a modal form triggered by a button."""

    def action(client):
        async def _action(client):
            from discli.utils import resolve_channel
            from discli.interact_engine import InteractEngine

            ch = resolve_channel(client, channel)
            engine = InteractEngine()

            fields = []
            for f in field:
                parts = f.split(":")
                label = parts[0]
                style = parts[1] if len(parts) > 1 else "short"
                required = parts[2].lower() == "required" if len(parts) > 2 else False
                fields.append({"label": label, "style": style, "required": required})

            # Send a button that triggers the modal
            view = discord.ui.View(timeout=300)
            btn = discord.ui.Button(
                label=f"Open: {title}",
                style=discord.ButtonStyle.primary,
                custom_id=f"modal:cli_{title.lower().replace(' ', '_')}",
            )
            view.add_item(btn)
            msg = await ch.send(content=f"Click to open: **{title}**", view=view)

            data = {
                "message_id": str(msg.id),
                "channel_id": str(ch.id),
                "title": title,
                "fields": fields,
            }
            output(ctx, data, plain_text=f"Modal trigger sent in #{ch.name} (click button to open)")

        return _action(client)

    run_discord(ctx, action)


@interact_group.group("workflow")
def workflow_group():
    """Manage interactive workflows."""


@workflow_group.command("start")
@click.argument("definition_file", type=click.Path(exists=True))
@click.option("--channel", required=True, help="Channel to run workflow in.")
@click.option("--user", required=True, help="Target user ID.")
@click.pass_context
def workflow_start(ctx, definition_file, channel, user):
    """Start a workflow from a JSON definition file."""

    def action(client):
        async def _action(client):
            from discli.utils import resolve_channel
            from discli.interact_engine import (
                InteractEngine, WorkflowDefinition, WorkflowStep,
            )

            ch = resolve_channel(client, channel)

            with open(definition_file) as f:
                raw = json.load(f)

            steps = [
                WorkflowStep(
                    step_id=s["step_id"],
                    step_type=s["step_type"],
                    content=s.get("content", ""),
                    components=s.get("components", []),
                    fields=s.get("fields", []),
                    next=s.get("next"),
                    timeout=s.get("timeout", 300),
                )
                for s in raw["steps"]
            ]
            wf_def = WorkflowDefinition(
                workflow_id=raw.get("workflow_id", definition_file),
                steps=steps,
            )

            engine = InteractEngine()
            key = await engine.workflow_start(ch, user, wf_def)
            output(ctx, {"workflow_key": key}, plain_text=f"Workflow started: {key}")

        return _action(client)

    run_discord(ctx, action)


@interact_group.group("dashboard")
def dashboard_group():
    """Manage persistent dashboards."""


@dashboard_group.command("create")
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("--channel", required=True, help="Channel for the dashboard.")
@click.pass_context
def dashboard_create(ctx, spec_file, channel):
    """Create a dashboard from a JSON spec file."""

    def action(client):
        async def _action(client):
            from discli.utils import resolve_channel
            from discli.interact_engine import (
                InteractEngine, DashboardDefinition, DashboardPage,
            )

            ch = resolve_channel(client, channel)

            with open(spec_file) as f:
                raw = json.load(f)

            pages = [
                DashboardPage(
                    embed=p.get("embed", {}),
                    components=p.get("components", []),
                )
                for p in raw.get("pages", [])
            ]
            dash_def = DashboardDefinition(
                dashboard_id=raw.get("dashboard_id", spec_file),
                pages=pages,
                refresh_interval=raw.get("refresh_interval", 0),
            )

            engine = InteractEngine()
            dash_id = await engine.dashboard_create(ch, dash_def)
            output(ctx, {"dashboard_id": dash_id}, plain_text=f"Dashboard created: {dash_id}")

        return _action(client)

    run_discord(ctx, action)


@dashboard_group.command("delete")
@click.argument("dashboard_id")
@click.option("--channel", required=True, help="Channel containing the dashboard.")
@click.pass_context
def dashboard_delete(ctx, dashboard_id, channel):
    """Delete a dashboard."""

    def action(client):
        async def _action(client):
            from discli.utils import resolve_channel
            from discli.interact_engine import InteractEngine

            ch = resolve_channel(client, channel)
            engine = InteractEngine()
            await engine.dashboard_delete(dashboard_id, ch)
            output(ctx, {"ok": True}, plain_text=f"Dashboard {dashboard_id} deleted")

        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register interact group in cli.py**

Add to `src/discli/cli.py`:

```python
from discli.commands.interact import interact_group
main.add_command(interact_group)
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```bash
git add src/discli/commands/interact.py src/discli/cli.py
git commit -m "feat: add interactive CLI commands (modal, workflow, dashboard)"
```

---

### Task 8: Serve Mode Integration — Voice Actions

**Files:**
- Modify: `src/discli/commands/serve.py`

**Step 1: Add voice engine initialization and actions to serve.py**

At the top of the `serve_cmd` function (after existing state variables around line 59), add:

```python
    # Voice engine (lazy init)
    voice_engine = None

    def _get_voice_engine():
        nonlocal voice_engine
        if voice_engine is None:
            from discli.voice_engine import VoiceEngine
            from discli.config import load_config
            config = load_config()
            voice_engine = VoiceEngine(config=config.get("voice", {}))
            voice_engine.set_event_handler(emit)
        return voice_engine
```

Add these action handlers (before the `_actions` dict):

```python
    async def _action_voice_connect(cmd: dict) -> dict:
        engine = _get_voice_engine()
        channel_id = cmd.get("channel_id")
        ch = client.get_channel(int(channel_id))
        if not ch or not isinstance(ch, discord.VoiceChannel):
            return {"error": f"Voice channel {channel_id} not found"}
        await engine.connect(ch)
        return {"ok": True, "channel_id": channel_id, "guild_id": str(ch.guild.id)}

    async def _action_voice_disconnect(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        await engine.disconnect(guild_id)
        return {"ok": True}

    async def _action_voice_move(cmd: dict) -> dict:
        engine = _get_voice_engine()
        channel_id = cmd.get("channel_id")
        ch = client.get_channel(int(channel_id))
        if not ch or not isinstance(ch, discord.VoiceChannel):
            return {"error": f"Voice channel {channel_id} not found"}
        await engine.move(ch)
        return {"ok": True, "channel_id": channel_id}

    async def _action_voice_speak(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        text = cmd.get("text", "")
        voice = cmd.get("voice", "default")
        speed = cmd.get("speed", 1.0)
        await engine.speak(guild_id, text, voice=voice, speed=speed)
        return {"ok": True}

    async def _action_voice_play(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        source = cmd.get("source", "")
        await engine.play(guild_id, source)
        return {"ok": True}

    async def _action_voice_stop(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        engine.stop(guild_id)
        return {"ok": True}

    async def _action_voice_pause(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        engine.pause(guild_id)
        return {"ok": True}

    async def _action_voice_resume(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        engine.resume(guild_id)
        return {"ok": True}

    async def _action_voice_listen_start(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        await engine.listen_start(guild_id)
        return {"ok": True}

    async def _action_voice_listen_stop(cmd: dict) -> dict:
        engine = _get_voice_engine()
        guild_id = cmd.get("guild_id")
        await engine.listen_stop(guild_id)
        return {"ok": True}

    async def _action_voice_status(cmd: dict) -> dict:
        engine = _get_voice_engine()
        return {"ok": True, "connections": engine.status()}

    async def _action_voice_set_config(cmd: dict) -> dict:
        engine = _get_voice_engine()
        updates = cmd.get("config", {})
        engine.update_config(updates)
        return {"ok": True, "config": engine.config}
```

Add to the `_actions` dict:

```python
        # Voice
        "voice_connect": _action_voice_connect,
        "voice_disconnect": _action_voice_disconnect,
        "voice_move": _action_voice_move,
        "voice_speak": _action_voice_speak,
        "voice_play": _action_voice_play,
        "voice_stop": _action_voice_stop,
        "voice_pause": _action_voice_pause,
        "voice_resume": _action_voice_resume,
        "voice_listen_start": _action_voice_listen_start,
        "voice_listen_stop": _action_voice_listen_stop,
        "voice_status": _action_voice_status,
        "voice_set_config": _action_voice_set_config,
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 3: Commit**

```bash
git add src/discli/commands/serve.py
git commit -m "feat: add voice actions to serve mode (connect, speak, play, listen, etc.)"
```

---

### Task 9: Serve Mode Integration — Interactive Actions

**Files:**
- Modify: `src/discli/commands/serve.py`

**Step 1: Add interact engine initialization and actions**

After the voice engine lazy init, add:

```python
    # Interactive engine (lazy init)
    interact_engine = None

    def _get_interact_engine():
        nonlocal interact_engine
        if interact_engine is None:
            from discli.interact_engine import InteractEngine
            interact_engine = InteractEngine()
            interact_engine.set_event_handler(emit)
        return interact_engine
```

Add these action handlers:

```python
    async def _action_workflow_start(cmd: dict) -> dict:
        engine = _get_interact_engine()
        from discli.interact_engine import WorkflowDefinition, WorkflowStep

        channel_id = cmd.get("channel_id")
        user_id = cmd.get("user_id")
        raw = cmd.get("workflow", {})

        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return {"error": f"Channel {channel_id} not found"}

        steps = [
            WorkflowStep(
                step_id=s["step_id"],
                step_type=s["step_type"],
                content=s.get("content", ""),
                components=s.get("components", []),
                fields=s.get("fields", []),
                next=s.get("next"),
                timeout=s.get("timeout", 300),
            )
            for s in raw.get("steps", [])
        ]
        wf_def = WorkflowDefinition(
            workflow_id=raw.get("workflow_id", str(uuid.uuid4())),
            steps=steps,
        )
        key = await engine.workflow_start(ch, user_id, wf_def)
        return {"ok": True, "workflow_key": key}

    async def _action_workflow_cancel(cmd: dict) -> dict:
        engine = _get_interact_engine()
        user_id = cmd.get("user_id")
        workflow_id = cmd.get("workflow_id")
        cancelled = engine.workflow_cancel(user_id, workflow_id)
        return {"ok": True, "cancelled": cancelled}

    async def _action_dashboard_create(cmd: dict) -> dict:
        engine = _get_interact_engine()
        from discli.interact_engine import DashboardDefinition, DashboardPage

        channel_id = cmd.get("channel_id")
        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return {"error": f"Channel {channel_id} not found"}

        raw = cmd.get("dashboard", {})
        pages = [
            DashboardPage(embed=p.get("embed", {}), components=p.get("components", []))
            for p in raw.get("pages", [])
        ]
        dash_def = DashboardDefinition(
            dashboard_id=raw.get("dashboard_id", str(uuid.uuid4())),
            pages=pages,
            refresh_interval=raw.get("refresh_interval", 0),
        )
        dash_id = await engine.dashboard_create(ch, dash_def)
        return {"ok": True, "dashboard_id": dash_id}

    async def _action_dashboard_update(cmd: dict) -> dict:
        engine = _get_interact_engine()
        dashboard_id = cmd.get("dashboard_id")
        channel_id = cmd.get("channel_id")
        updates = cmd.get("updates", {})

        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return {"error": f"Channel {channel_id} not found"}

        await engine.dashboard_update(dashboard_id, updates, ch)
        return {"ok": True}

    async def _action_dashboard_delete(cmd: dict) -> dict:
        engine = _get_interact_engine()
        dashboard_id = cmd.get("dashboard_id")
        channel_id = cmd.get("channel_id")

        ch = resolve_channel_by_id(channel_id)
        if not ch:
            return {"error": f"Channel {channel_id} not found"}

        await engine.dashboard_delete(dashboard_id, ch)
        return {"ok": True}
```

Add to the `_actions` dict:

```python
        # Workflows & Dashboards
        "workflow_start": _action_workflow_start,
        "workflow_cancel": _action_workflow_cancel,
        "dashboard_create": _action_dashboard_create,
        "dashboard_update": _action_dashboard_update,
        "dashboard_delete": _action_dashboard_delete,
```

**Step 2: Update the `on_interaction` handler to route to interact engine**

In the existing `on_interaction` handler (around line 398), add routing for workflow and dashboard interactions after the existing modal_submit handling:

```python
        # Route prefixed interactions to interact engine
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            engine = _get_interact_engine()
            route = engine.route_custom_id(custom_id)
            if route == "workflow":
                await engine.handle_workflow_interaction(interaction, custom_id)
                return
            elif route == "dashboard":
                await engine.handle_dashboard_interaction(interaction, custom_id)
                return
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```bash
git add src/discli/commands/serve.py
git commit -m "feat: add interactive actions to serve mode (workflows, dashboards)"
```

---

### Task 10: Update Security Profiles

**Files:**
- Modify: `src/discli/security.py`
- Create: `tests/test_security_voice.py`

**Step 1: Write the failing test**

Create `tests/test_security_voice.py`:

```python
from discli.security import is_command_allowed


def test_readonly_denies_voice_join():
    assert not is_command_allowed("voice join", profile_override="readonly")


def test_readonly_allows_voice_status():
    assert is_command_allowed("voice status", profile_override="readonly")


def test_chat_allows_interact():
    assert is_command_allowed("interact modal", profile_override="chat")


def test_chat_denies_voice():
    assert not is_command_allowed("voice join", profile_override="chat")


def test_full_allows_voice():
    assert is_command_allowed("voice join", profile_override="full")


def test_full_allows_interact():
    assert is_command_allowed("interact dashboard create", profile_override="full")


def test_moderation_allows_voice():
    assert is_command_allowed("voice join", profile_override="moderation")


def test_moderation_allows_interact():
    assert is_command_allowed("interact workflow start", profile_override="moderation")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_security_voice.py -v`
Expected: some FAIL (readonly doesn't have voice status allowed, chat doesn't have interact)

**Step 3: Update security.py profiles**

In `src/discli/security.py`, update `DEFAULT_PROFILES`:

```python
DEFAULT_PROFILES = {
    "full": {
        "description": "Full access to all commands",
        "allowed": ["*"],
        "denied": [],
    },
    "chat": {
        "description": "Messages, reactions, threads, typing, interactions only",
        "allowed": ["message", "reaction", "thread", "typing", "dm", "listen", "serve", "config", "server", "interact"],
        "denied": ["member kick", "member ban", "member unban", "channel delete", "role delete", "role create", "channel create", "voice"],
    },
    "readonly": {
        "description": "Read-only: list, info, get, search, listen",
        "allowed": ["message list", "message get", "message search", "message history", "channel list", "channel info", "server list", "server info", "role list", "member list", "member info", "reaction list", "thread list", "listen", "config show", "voice status"],
        "denied": ["*"],
    },
    "moderation": {
        "description": "Full access including moderation, voice, and interactions",
        "allowed": ["*"],
        "denied": [],
    },
}
```

**Step 4: Run tests**

Run: `pytest tests/test_security_voice.py -v`
Expected: 8 PASS

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 6: Commit**

```bash
git add src/discli/security.py tests/test_security_voice.py
git commit -m "feat: update permission profiles with voice and interact scopes"
```

---

### Task 11: Update Documentation

**Files:**
- Modify: `agents/discord-agent.md` (if it exists — add voice and interact command reference)
- Modify: `CLAUDE.md` (add voice/interact to architecture notes)

**Step 1: Update CLAUDE.md**

Add voice and interact to the key modules section and commands list.

**Step 2: Commit**

```bash
git add CLAUDE.md agents/discord-agent.md
git commit -m "docs: add voice and interactive features to documentation"
```

---

### Task 12: Version Bump and Final Verification

**Files:**
- Modify: `pyproject.toml` (version bump to 0.8.0)

**Step 1: Bump version**

Change `version = "0.7.0"` to `version = "0.8.0"` in `pyproject.toml`.

**Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 3: Verify install**

Run: `pip install -e ".[dev]"`
Expected: clean install

**Step 4: Verify CLI help includes new commands**

Run: `discli --help`
Expected: voice and interact groups listed

Run: `discli voice --help`
Expected: join, leave, speak, play, stop, pause, resume, listen, status

Run: `discli interact --help`
Expected: modal, workflow, dashboard

**Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 0.8.0"
```
