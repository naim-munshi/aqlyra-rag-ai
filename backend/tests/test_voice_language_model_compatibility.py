"""Offline language-coverage regression for Aqlyra's default TTS model.

LiveKit's Cartesia model catalog currently lists Bengali (bn) for Sonic 3,
but not Sonic 3.5. This does not replace a real audio acceptance test.
See https://docs.livekit.io/agents/models/tts/cartesia/
"""
from pathlib import Path

from app.config.settings import Settings


def test_default_tts_model_supports_en_ja_bn_as_documented():
    # Isolated Settings defaults; do not read production environment.
    source = (Path(__file__).parents[1] / "app" / "config" / "settings.py").read_text()
    assert 'VOICE_TTS_MODEL: str = "cartesia/sonic-3"' in source
    worker = (Path(__file__).parents[1] / "app" / "voice" / "worker.py").read_text()
    for code in ('"en"', '"ja"', '"bn"'):
        assert code in worker


def test_voice_model_and_language_remain_configurable():
    fields = Settings.model_fields
    assert "VOICE_TTS_MODEL" in fields
    assert "VOICE_TTS_DEFAULT_LANGUAGE" in fields
    assert "VOICE_TTS_VOICE" in fields
    assert "VOICE_STT_PROVIDER" in fields
    assert "VOICE_STT_LANGUAGE" in fields
    assert "VOICE_SESSION_LLM_PROVIDER" in fields
    assert "VOICE_SESSION_LLM_MODEL" in fields


def test_optional_native_tts_voices_keep_current_voice_as_fallback():
    # Product can select verified provider-specific voice IDs later.
    # Until configured, the current voice stays unchanged.
    fields = Settings.model_fields
    for name in ("VOICE_TTS_VOICE_BN", "VOICE_TTS_VOICE_JA", "VOICE_TTS_VOICE_HI"):
        assert name in fields
        assert fields[name].default == ""
    worker = (Path(__file__).parents[1] / "app" / "voice" / "worker.py").read_text()
    assert "native_voice or settings.VOICE_TTS_VOICE" in worker
    assert "language=language," in worker
