import os
import pytest

from discli.stt import STTError, STTProvider, TranscriptionResult, get_stt_provider


def test_get_stt_provider_unknown_raises():
    with pytest.raises(STTError, match="unknown"):
        get_stt_provider("nonexistent_provider")


def test_stt_provider_protocol_has_required_methods():
    assert hasattr(STTProvider, "transcribe")
    assert hasattr(STTProvider, "close")


def test_transcription_result_fields():
    result = TranscriptionResult(text="hello world", confidence=0.95, is_final=True)
    assert result.text == "hello world"
    assert result.confidence == 0.95
    assert result.is_final is True
    assert result.user_id is None

    result_with_user = TranscriptionResult(
        text="hi", confidence=0.8, is_final=False, user_id="123456789"
    )
    assert result_with_user.user_id == "123456789"


def test_get_stt_provider_deepgram_missing_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises(STTError, match="DEEPGRAM_API_KEY"):
        get_stt_provider("deepgram")
