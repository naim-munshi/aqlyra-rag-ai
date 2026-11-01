"""Offline worker boot gates; does not call LiveKit/Groq or use live secrets."""
import pytest
from app.voice.preflight import (
    REQUIRED, VoiceWorkerPreflightError, validate_voice_worker_environment,
)


def valid_env():
    return {
        "APP_ENV": "production",
        "SECRET_KEY": "s" * 48,
        "DATABASE_URL": "postgresql+psycopg://user:fake@db.example.com:5432/voice",
        "REDIS_URL": "rediss://redis.example.com:6380",
        "LIVEKIT_URL": "wss://example.livekit.cloud",
        "LIVEKIT_API_KEY": "test-non-production-key",
        "LIVEKIT_API_SECRET": "s" * 42,
        "VOICE_AGENT_NAME": "aqlyra-voice",
        "GROQ_API_KEY": "test-placeholder-key",
        "VOICE_STT_MODEL": "whisper-large-v3",
        "VOICE_TTS_MODEL": "cartesia/sonic-3",
        "VOICE_TTS_VOICE": "fake-voice",
    }


def test_all_configured_passes_offline():
    validate_voice_worker_environment(valid_env())


@pytest.mark.parametrize("key", REQUIRED)
def test_missing_required_key_blocks_start_and_never_discloses_value(key):
    data = valid_env()
    data[key] = ""
    with pytest.raises(VoiceWorkerPreflightError) as exc:
        validate_voice_worker_environment(data)
    assert key in str(exc.value)
    assert "test-non-production-key" not in str(exc.value)


@pytest.mark.parametrize("url", [
    "ws://example.livekit.cloud", "wss://127.0.0.1", "wss://localhost",
    "wss://169.254.169.254", "wss://private.internal",
    "wss://user:pass@example.livekit.cloud", "wss://example.livekit.cloud?token=secret",
    "wss://example.livekit.cloud/path", "not-a-url",
])
def test_insecure_livekit_endpoint_blocks_worker(url):
    data = valid_env()
    data["LIVEKIT_URL"] = url
    with pytest.raises(VoiceWorkerPreflightError, match="LIVEKIT_URL"):
        validate_voice_worker_environment(data)


def test_worker_never_boots_in_unreviewed_development_mode():
    data = valid_env()
    data["APP_ENV"] = "development"
    with pytest.raises(VoiceWorkerPreflightError, match="APP_ENV"):
        validate_voice_worker_environment(data)


def test_weak_secret_blocks_worker():
    data = valid_env()
    data["SECRET_KEY"] = "weak"
    with pytest.raises(VoiceWorkerPreflightError, match="SECRET_KEY"):
        validate_voice_worker_environment(data)


@pytest.mark.parametrize("key,value", [
    ("DATABASE_URL", "sqlite:///voice.db"),
    ("REDIS_URL", "http://localhost"),
    ("VOICE_AGENT_NAME", "../wrong-room"),
])
def test_incompatible_backend_or_agent_settings_block_worker(key, value):
    data = valid_env()
    data[key] = value
    with pytest.raises(VoiceWorkerPreflightError):
        validate_voice_worker_environment(data)
