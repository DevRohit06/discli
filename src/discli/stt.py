"""Speech-to-text provider protocol and implementations for discli."""

from __future__ import annotations

import asyncio
import io
import os
import wave
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable


class STTError(Exception):
    """Raised for STT configuration or runtime errors."""


@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    is_final: bool
    user_id: str | None = None


@runtime_checkable
class STTProvider(Protocol):
    async def transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        *,
        sample_rate: int = 48000,
    ) -> AsyncIterator[TranscriptionResult]: ...

    async def close(self) -> None: ...


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise STTError(f"{name} environment variable is required but not set")
    return value


class DeepgramSTT:
    """Streaming STT via Deepgram's live transcription websocket API."""

    SUPPORTS_STREAMING = True

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _get_async_client(self):
        try:
            from deepgram import AsyncDeepgramClient  # type: ignore[import]
        except ImportError as exc:
            raise STTError(
                "deepgram-sdk is not installed. Run: pip install discord-cli-agent[deepgram]"
            ) from exc
        return AsyncDeepgramClient(api_key=self._api_key)

    async def transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        *,
        sample_rate: int = 48000,
    ) -> AsyncIterator[TranscriptionResult]:
        """Batch-style transcription kept for backwards compatibility with
        callers that buffer audio before transcribing. For real-time meeting
        transcription, use :meth:`stream_session` instead."""
        async for result in self.stream_session(audio_stream, sample_rate=sample_rate):
            yield result

    async def stream_session(
        self,
        audio_stream: AsyncIterator[bytes],
        *,
        sample_rate: int = 48000,
        channels: int = 1,
        model: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream audio to Deepgram's live transcription websocket and yield
        ``TranscriptionResult`` objects as they arrive.

        Talks to Deepgram directly via ``websockets`` — the official
        ``deepgram-sdk`` v6.x ``listen.v1.connect`` helper has a generic 400
        "Unexpected error when initializing websocket connection" bug for our
        flow, while the raw API works fine.
        """
        try:
            import websockets  # type: ignore[import]
        except ImportError as exc:
            raise STTError(
                "websockets is not installed. Run: pip install websockets "
                "(comes in via discord-cli-agent[deepgram])"
            ) from exc

        import json as _json
        from urllib.parse import urlencode

        if model is None:
            model = os.environ.get("DISCLI_DEEPGRAM_MODEL", "nova-3")
        if language is None:
            language = os.environ.get("DISCLI_DEEPGRAM_LANGUAGE", "multi")

        params = {
            "model": model,
            "language": language,
            "encoding": "linear16",
            "sample_rate": str(sample_rate),
            "channels": str(channels),
            "interim_results": "true",
            "punctuate": "true",
            "smart_format": "true",
        }
        url = f"wss://api.deepgram.com/v1/listen?{urlencode(params)}"
        headers = {"Authorization": f"Token {self._api_key}"}

        async with websockets.connect(
            url, additional_headers=headers, open_timeout=10
        ) as ws:
            stop = asyncio.Event()

            # Drain the audio_stream into a small inner queue so we can
            # multiplex audio sends with periodic KeepAlive messages.
            # Without KeepAlives Deepgram closes the connection with
            # error 1011 after ~10s of silence.
            inner: asyncio.Queue = asyncio.Queue(maxsize=500)

            async def _drain():
                try:
                    async for chunk in audio_stream:
                        if chunk:
                            await inner.put(chunk)
                finally:
                    await inner.put(None)  # sentinel: source closed

            async def _pump():
                packets_sent = 0
                try:
                    while not stop.is_set():
                        try:
                            chunk = await asyncio.wait_for(inner.get(), timeout=3.0)
                        except asyncio.TimeoutError:
                            # No audio in the last 3s — keep the websocket warm.
                            await ws.send(_json.dumps({"type": "KeepAlive"}))
                            continue
                        if chunk is None:
                            break
                        await ws.send(chunk)
                        packets_sent += 1
                    print(
                        f"[stt] pump exiting after {packets_sent} packets",
                        flush=True,
                    )
                    try:
                        await ws.send(_json.dumps({"type": "Finalize"}))
                        await ws.send(_json.dumps({"type": "CloseStream"}))
                    except Exception:
                        pass
                finally:
                    stop.set()

            drain_task = asyncio.create_task(_drain())
            pump_task = asyncio.create_task(_pump())

            try:
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    try:
                        msg = _json.loads(raw)
                    except _json.JSONDecodeError:
                        continue
                    mtype = msg.get("type")
                    print(f"[stt] dg msg type={mtype}", flush=True)
                    if mtype != "Results":
                        continue
                    channel = msg.get("channel") or {}
                    alts = channel.get("alternatives") or []
                    if not alts:
                        continue
                    transcript = alts[0].get("transcript") or ""
                    if not transcript:
                        continue
                    yield TranscriptionResult(
                        text=transcript,
                        confidence=float(alts[0].get("confidence") or 0.0),
                        is_final=bool(msg.get("is_final")),
                    )
            finally:
                stop.set()
                for t in (pump_task, drain_task):
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

    async def close(self) -> None:
        pass


class OpenAISTT:
    """Batch STT via OpenAI Whisper API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        try:
            from openai import AsyncOpenAI  # type: ignore[import]
        except ImportError as exc:
            raise STTError(
                "openai is not installed. Run: pip install discord-cli-agent[openai-voice]"
            ) from exc
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        *,
        sample_rate: int = 48000,
    ) -> AsyncIterator[TranscriptionResult]:
        # Collect all audio chunks
        chunks: list[bytes] = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        raw_audio = b"".join(chunks)

        # Wrap in a WAV container
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(raw_audio)
        buf.seek(0)
        buf.name = "audio.wav"

        client = self._get_client()
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )

        yield TranscriptionResult(
            text=response.text,
            confidence=1.0,
            is_final=True,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


def get_stt_provider(name: str) -> STTProvider:
    """Factory that returns an STTProvider instance for the given name."""
    name = name.lower()
    if name == "deepgram":
        api_key = _require_env("DEEPGRAM_API_KEY")
        return DeepgramSTT(api_key)
    if name == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        return OpenAISTT(api_key)
    raise STTError(f"unknown STT provider: {name!r}")
