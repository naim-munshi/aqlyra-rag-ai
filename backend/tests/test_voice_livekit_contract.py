"""Offline security and functional contract checks for LiveKit voice sessions.

These do not prove real WebRTC/STT/TTS availability: a separately deployed
aqlyra-voice worker, actual provider credentials and a browser are required.
"""
import base64
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config.settings import settings
from app.services import voice_session_service as voice


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "LIVEKIT_URL", "wss://voice.test.invalid")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "voice-test-key")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "voice-test-secret-do-not-use")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "VOICE_STT_PROVIDER", "livekit")
    monkeypatch.setattr(settings, "VOICE_STT_MODEL", "deepgram/nova-3")
    monkeypatch.setattr(settings, "VOICE_STT_LANGUAGE", "multi")
    monkeypatch.setattr(settings, "VOICE_SESSION_LLM_PROVIDER", "livekit")
    monkeypatch.setattr(settings, "VOICE_SESSION_LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "VOICE_TTS_MODEL", "cartesia/sonic-3")
    monkeypatch.setattr(settings, "VOICE_TTS_VOICE", "test-tts-voice")
    monkeypatch.setattr(settings, "VOICE_AGENT_NAME", "aqlyra-voice")
    monkeypatch.setattr(settings, "VOICE_AGENT_READY", True)
    # Offline contract tests must never dispatch a real billable job.
    monkeypatch.setattr(voice, "_dispatch_voice_agent", lambda **_: None)


def _jwt_claims(token: str) -> dict:
    parts = token.split(".")
    assert len(parts) == 3
    encoded = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded))


@pytest.mark.parametrize(
    "missing", [
        "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
        "VOICE_STT_MODEL", "VOICE_STT_LANGUAGE", "VOICE_TTS_MODEL",
        "VOICE_TTS_VOICE",
    ]
)
def test_missing_voice_provider_credentials_fail_closed(monkeypatch, missing):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, missing, "")

    with pytest.raises(voice.VoiceConfigurationError, match="not configured"):
        voice._require_voice_configuration()


def test_explicit_worker_acceptance_required_before_tokens(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "VOICE_AGENT_READY", False)
    assert voice.voice_is_ready() is False
    with pytest.raises(voice.VoiceConfigurationError, match="not configured"):
        voice._require_voice_configuration()


def test_authenticated_voice_status_never_exposes_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "VOICE_AGENT_READY", False)
    response = client.get("/api/v1/voice/status")
    assert response.status_code == 401
    assert "participant_token" not in response.text


def test_missing_worker_agent_name_fails_closed(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "VOICE_AGENT_NAME", "")

    with pytest.raises(voice.VoiceConfigurationError, match="VOICE_AGENT_NAME"):
        voice._require_voice_configuration()


def test_voice_room_token_is_user_scoped_and_dispatches_named_worker(monkeypatch):
    _configure(monkeypatch)
    owner_id = uuid4()
    conversation_id = uuid4()
    user = SimpleNamespace(id=owner_id, username="voice-owner")
    conversation = SimpleNamespace(id=conversation_id, mode="knowledge")
    documents = (str(uuid4()), str(uuid4()))
    observed = {}

    def resolve(**kwargs):
        observed["resolved_owner"] = kwargs["user"].id
        observed["mode"] = kwargs["mode"]
        return conversation

    def validate(**kwargs):
        observed["documents_owner"] = kwargs["user"].id
        observed["documents"] = kwargs["document_ids"]

    monkeypatch.setattr(voice, "_resolve_conversation", resolve)
    monkeypatch.setattr(voice, "_validate_documents", validate)

    dispatched = {}
    monkeypatch.setattr(
        voice, "_dispatch_voice_agent", lambda **kwargs: dispatched.update(kwargs)
    )
    result = voice.create_voice_session(
        db=object(), user=user, mode="knowledge",
        conversation_id=str(conversation_id), title="Voice session",
        document_ids=documents,
    )
    claims = _jwt_claims(result.participant_token)
    # Joining authority lasts 10 minutes, not the SDK's multi-hour default.
    assert 0 < claims["exp"] - int(time.time()) <= 610
    grant = claims["video"]
    assert result.server_url == "wss://voice.test.invalid"
    assert result.mode == "knowledge"
    assert result.conversation_id == str(conversation_id)
    assert result.room_name.startswith("aqlyra-voice-")
    assert str(owner_id) not in result.room_name
    assert str(conversation_id) not in result.room_name
    assert grant["roomJoin"] is True
    assert grant["room"] == result.room_name
    assert grant["canSubscribe"] is True
    assert grant["canPublish"] is True
    assert grant["canPublishSources"] == ["microphone"]
    assert grant["canPublishData"] is False
    assert grant["canUpdateOwnMetadata"] is False
    assert claims["sub"].startswith("voice-")
    assert str(owner_id) not in claims["sub"]
    assert claims.get("metadata") in (None, "")
    assert claims.get("name") == "Aqlyra Voice"
    assert observed == {
        "resolved_owner": owner_id,
        "mode": "knowledge",
        "documents_owner": owner_id,
        "documents": documents,
    }

    metadata = {
        "user_id": str(owner_id),
        "conversation_id": str(conversation_id),
        "mode": "knowledge",
        "document_ids": list(documents),
    }
    assert metadata == {
        "user_id": str(owner_id),
        "conversation_id": str(conversation_id),
        "mode": "knowledge",
        "document_ids": list(documents),
    }
    # Server-side explicit dispatch must not be duplicated by JWT room config.
    assert claims.get("roomConfig") in (None, {})
    assert dispatched["room_name"] == result.room_name
    assert json.loads(dispatched["metadata"]) == metadata
    assert "voice-test-secret-do-not-use" not in result.participant_token


def test_foreign_or_unready_document_rejection_stops_token_issue(monkeypatch):
    _configure(monkeypatch)
    user = SimpleNamespace(id=uuid4(), username="voice-owner")
    conversation = SimpleNamespace(id=uuid4(), mode="knowledge")
    monkeypatch.setattr(
        voice, "_resolve_conversation", lambda **_: conversation,
    )

    def deny(**_):
        raise voice.VoiceDocumentValidationError(
            "One or more selected documents are not available"
        )

    monkeypatch.setattr(voice, "_validate_documents", deny)
    with pytest.raises(voice.VoiceDocumentValidationError):
        voice.create_voice_session(
            db=object(), user=user, mode="knowledge",
            conversation_id=str(conversation.id), title="Voice",
            document_ids=(str(uuid4()),),
        )


def test_anonymous_browser_cannot_request_voice_room(client):
    response = client.post(
        "/api/v1/voice/session",
        json={"mode": "normal", "document_ids": []},
    )
    assert response.status_code == 401
    assert "participant_token" not in response.text

@pytest.mark.parametrize("provider_setting", [
    "VOICE_STT_PROVIDER", "VOICE_SESSION_LLM_PROVIDER", "LLM_PROVIDER",
])
def test_explicit_groq_provider_still_requires_key(monkeypatch, provider_setting):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, provider_setting, "groq")
    with pytest.raises(voice.VoiceConfigurationError, match="not configured"):
        voice._require_voice_configuration()


def test_livekit_readiness_diagnostics_never_return_secret_values(monkeypatch):
    _configure(monkeypatch)
    secret = "ultra-private-synthetic-token-not-for-logs"
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", secret)
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "")
    missing = voice.missing_voice_configuration_keys()
    assert "LIVEKIT_API_KEY" in missing
    assert "LIVEKIT_API_SECRET" not in missing
    assert secret not in str(missing)
    assert not voice.voice_is_ready()


def test_livekit_readiness_diagnostics_require_feature_gate(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "VOICE_AGENT_READY", False)
    assert "VOICE_AGENT_READY" in voice.missing_voice_configuration_keys()
    assert not voice.voice_is_ready()


def test_livekit_readiness_diagnostics_valid_configuration(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "LIVEKIT_URL", "wss://aqlyra-whhfocpe.livekit.cloud/")
    assert voice.missing_voice_configuration_keys() == ()
    assert voice.voice_is_ready()
