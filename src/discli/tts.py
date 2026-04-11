"""TTS provider protocol and implementations for ElevenLabs and OpenAI."""

from __future__ import annotations

import os
from typing import AsyncIterator, Protocol, runtime_checkable


class TTSError(Exception):
    """Raised for TTS configuration or runtime errors."""


def _require_env(name: str) -> str:
    """Return the value of env var *name*, or raise TTSError if not set."""
    value = os.environ.get(name)
    if not value:
        raise TTSError(f"Environment variable {name} is not set")
    return value


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...


class ElevenLabsTTS:
    """TTS provider backed by the ElevenLabs SDK."""

    def __init__(self, api_key: str) -> None:
        try:
            from elevenlabs.client import AsyncElevenLabs  # type: ignore[import]
        except ImportError as exc:
            raise TTSError(
                "elevenlabs package is not installed. Run: pip install elevenlabs"
            ) from exc
        self._client = AsyncElevenLabs(api_key=api_key)

    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        stream = await self._client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice,
            output_format="pcm_24000",
        )
        async for chunk in stream:
            yield chunk

    async def close(self) -> None:
        await self._client.close()


class OpenAITTS:
    """TTS provider backed by the OpenAI SDK."""

    def __init__(self, api_key: str) -> None:
        try:
            from openai import AsyncOpenAI  # type: ignore[import]
        except ImportError as exc:
            raise TTSError(
                "openai package is not installed. Run: pip install openai"
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key)

    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        response = await self._client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="pcm",
            speed=speed,
        )
        async for chunk in response.iter_bytes():
            yield chunk

    async def close(self) -> None:
        await self._client.close()


def get_tts_provider(name: str) -> ElevenLabsTTS | OpenAITTS:
    """Return a TTS provider instance for *name*.

    Raises TTSError for unknown provider names or missing API keys.
    """
    if name == "elevenlabs":
        api_key = _require_env("ELEVENLABS_API_KEY")
        return ElevenLabsTTS(api_key=api_key)
    if name == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        return OpenAITTS(api_key=api_key)
    raise TTSError(f"unknown TTS provider: {name!r}. Supported providers: elevenlabs, openai")
