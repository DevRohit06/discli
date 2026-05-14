import os
import pytest

from discli.tts import TTSError, TTSProvider, get_tts_provider


def test_get_tts_provider_unknown_raises():
    with pytest.raises(TTSError, match="unknown"):
        get_tts_provider("nonexistent_provider")


def test_tts_provider_protocol_has_required_methods():
    assert hasattr(TTSProvider, "synthesize")
    assert hasattr(TTSProvider, "close")


def test_get_tts_provider_elevenlabs_missing_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(TTSError, match="ELEVENLABS_API_KEY"):
        get_tts_provider("elevenlabs")
