"""Fail-closed LiveKit WebSocket configuration before issuing client JWTs."""
import pytest

from app.config.settings import settings
from app.services import voice_session_service as voice


@pytest.mark.parametrize("endpoint", [
    "ws://voice.example.com",
    "https://voice.example.com",
    "http://voice.example.com",
    "wss://localhost",
    "wss://127.0.0.1",
    "wss://10.0.0.3",
    "wss://169.254.169.254",
    "wss://[::1]",
    "wss://voice.internal",
    "wss://voice.local",
    "wss://user:pass@voice.example.com",
    "wss://voice.example.com?token=secret",
    "wss://voice.example.com/private-path",
    "wss://voice.example.com:99999",
    "not-a-url",
])
def test_production_refuses_insecure_or_private_transport(endpoint):
    assert voice._valid_livekit_url(endpoint, production=True) is False


@pytest.mark.parametrize("endpoint", [
    "wss://voice.livekit.cloud",
    "wss://example.livekit.cloud:443",
])
def test_production_accepts_public_secure_livekit_hosts(endpoint):
    assert voice._valid_livekit_url(endpoint, production=True) is True


def test_development_may_use_plaintext_local_livekit():
    assert voice._valid_livekit_url("ws://localhost:7880", production=False)


def test_ready_flag_cannot_override_invalid_production_transport(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "VOICE_AGENT_READY", True)
    monkeypatch.setattr(settings, "LIVEKIT_URL", "ws://127.0.0.1:7880")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "not-a-real-secret")
    monkeypatch.setattr(settings, "VOICE_AGENT_NAME", "aqlyra-voice")
    assert voice.voice_is_ready() is False
    with pytest.raises(voice.VoiceConfigurationError, match="safely configured"):
        voice._require_voice_configuration()
