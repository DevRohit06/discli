"""Speech-to-text provider protocol and implementations for discli."""

from __future__ import annotations

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

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        try:
            from deepgram import DeepgramClient  # type: ignore[import]
        except ImportError as exc:
            raise STTError(
                "deepgram-sdk is not installed. Run: pip install discord-cli-agent[deepgram]"
            ) from exc
        if self._client is None:
            self._client = DeepgramClient(self._api_key)
        return self._client

    async def transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        *,
        sample_rate: int = 48000,
    ) -> AsyncIterator[TranscriptionResult]:
        try:
            from deepgram import LiveOptions, LiveTranscriptionEvents  # type: ignore[import]
        except ImportError as exc:
            raise STTError(
                "deepgram-sdk is not installed. Run: pip install discord-cli-agent[deepgram]"
            ) from exc

        client = self._get_client()
        connection = client.listen.asyncwebsocket.v("1")

        results: list[TranscriptionResult] = []

        def on_transcript(self_inner, result, **kwargs):  # noqa: ANN001
            sentence = result.channel.alternatives[0]
            if sentence.transcript:
                results.append(
                    TranscriptionResult(
                        text=sentence.transcript,
                        confidence=sentence.confidence,
                        is_final=result.is_final,
                    )
                )

        connection.on(LiveTranscriptionEvents.Transcript, on_transcript)

        options = LiveOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            encoding="linear16",
            interim_results=True,
            sample_rate=sample_rate,
        )

        await connection.start(options)

        async for chunk in audio_stream:
            await connection.send(chunk)

        await connection.finish()

        for result in results:
            yield result

    async def close(self) -> None:
        self._client = None


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
