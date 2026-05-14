"""Tests for VoiceEngine core — connection management, config, and error handling."""

from __future__ import annotations

import pytest

from discli.voice_engine import (
    DEFAULT_CONFIG,
    VoiceEngine,
    VoiceError,
    install_voice_recv_patches,
)


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


def test_install_voice_recv_patches_idempotent():
    """Calling the patch installer repeatedly must not stack monkeypatches."""
    pytest.importorskip("discord.ext.voice_recv")
    pytest.importorskip("davey")

    from discord.ext.voice_recv.opus import PacketDecoder

    # Save the originals to restore after the test so we don't pollute the
    # module for other tests that may depend on pristine class methods.
    orig_decode = PacketDecoder._decode_packet
    orig_pop = PacketDecoder.pop_data
    had_dave_flag = getattr(PacketDecoder, "_discli_dave_patched", False)
    had_pop_flag = getattr(PacketDecoder, "_discli_pop_patched", False)

    try:
        # Clear any flag a previous test/run left behind so we install fresh.
        for attr in ("_discli_dave_patched", "_discli_pop_patched"):
            if hasattr(PacketDecoder, attr):
                delattr(PacketDecoder, attr)

        assert install_voice_recv_patches() is True
        first_decode = PacketDecoder._decode_packet
        first_pop = PacketDecoder.pop_data
        assert PacketDecoder._discli_dave_patched is True
        assert PacketDecoder._discli_pop_patched is True
        assert first_decode is not orig_decode
        assert first_pop is not orig_pop

        # Second call must be a no-op — same wrapped methods, not re-wrapped.
        assert install_voice_recv_patches() is True
        assert PacketDecoder._decode_packet is first_decode
        assert PacketDecoder.pop_data is first_pop
    finally:
        # Restore originals so the rest of the suite sees a clean class.
        PacketDecoder._decode_packet = orig_decode
        PacketDecoder.pop_data = orig_pop
        if not had_dave_flag and hasattr(PacketDecoder, "_discli_dave_patched"):
            delattr(PacketDecoder, "_discli_dave_patched")
        if not had_pop_flag and hasattr(PacketDecoder, "_discli_pop_patched"):
            delattr(PacketDecoder, "_discli_pop_patched")
