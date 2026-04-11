"""Tests for VoiceEngine core — connection management, config, and error handling."""

from __future__ import annotations

import pytest

from discli.voice_engine import DEFAULT_CONFIG, VoiceEngine, VoiceError


def test_voice_engine_instantiates():
    engine = VoiceEngine()
    assert engine.connections == {}


def test_voice_engine_get_connection_not_connected():
    engine = VoiceEngine()
    with pytest.raises(VoiceError, match="Not connected"):
        engine.get_connection(123456789)


def test_voice_engine_config_defaults():
    engine = VoiceEngine()
    assert engine.config["tts_provider"] == "elevenlabs"
    assert engine.config["stt_provider"] == "deepgram"
    assert engine.config["vad_threshold"] == 0.5
    assert engine.config["silence_duration_ms"] == 800
    assert engine.config["playback_volume"] == 1.0


def test_voice_engine_update_config():
    engine = VoiceEngine()
    engine.update_config({"playback_volume": 0.5, "vad_threshold": 0.8})
    assert engine.config["playback_volume"] == 0.5
    assert engine.config["vad_threshold"] == 0.8
    # Unchanged values stay
    assert engine.config["tts_provider"] == "elevenlabs"
    assert engine.config["stt_provider"] == "deepgram"
    assert engine.config["silence_duration_ms"] == 800
