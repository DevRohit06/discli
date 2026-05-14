"""TTS provider protocol and implementations for ElevenLabs, OpenAI, and Deepgram Aura."""

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


class DeepgramTTS:
    """TTS provider backed by Deepgram Aura via the deepgram-sdk async REST API."""

    # Default Aura 2 voice. Override by passing ``voice="aura-2-thalia-en"`` etc.
    DEFAULT_MODEL = "aura-2-asteria-en"
    # 16-bit signed little-endian mono PCM — matches what ElevenLabs/OpenAI emit.
    SAMPLE_RATE = 24000

    def __init__(self, api_key: str) -> None:
        try:
            from deepgram import AsyncDeepgramClient  # type: ignore[import]
        except ImportError as exc:
            raise TTSError(
                "deepgram-sdk is not installed. Run: pip install discord-cli-agent[deepgram]"
            ) from exc
        self._client = AsyncDeepgramClient(api_key=api_key)

    async def synthesize(
        self, text: str, *, voice: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        # Aura selects the voice via the model name (e.g. aura-2-asteria-en).
        # If the caller passes an empty/sentinel value OR a voice name that
        # doesn't look like an Aura model, fall back to DEFAULT_MODEL rather
        # than letting Deepgram reject it (common when a bot is switched from
        # OpenAI/ElevenLabs without updating the voice setting).
        if voice in ("default", "", None) or not str(voice).startswith("aura"):
            model = self.DEFAULT_MODEL
        else:
            model = voice
        # AsyncDeepgramClient.speak.v1.audio.generate is an async generator
        # that yields raw audio chunks — iterate it directly.
        async for chunk in self._client.speak.v1.audio.generate(
            text=text,
            model=model,
            encoding="linear16",
            sample_rate=self.SAMPLE_RATE,
        ):
            if chunk:
                yield chunk

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            result = close()
            if hasattr(result, "__await__"):
                await result


def get_tts_provider(name: str) -> ElevenLabsTTS | OpenAITTS | DeepgramTTS:
    """Return a TTS provider instance for *name*.

    Raises TTSError for unknown provider names or missing API keys.
    """
    if name == "elevenlabs":
        api_key = _require_env("ELEVENLABS_API_KEY")
        return ElevenLabsTTS(api_key=api_key)
    if name == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        return OpenAITTS(api_key=api_key)
    if name == "deepgram":
        api_key = _require_env("DEEPGRAM_API_KEY")
        return DeepgramTTS(api_key=api_key)
    raise TTSError(
        f"unknown TTS provider: {name!r}. Supported providers: elevenlabs, openai, deepgram"
    )
