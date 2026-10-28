"""Offline security and functional contract checks for LiveKit voice sessions.

These do not prove real WebRTC/STT/TTS availability: a separately deployed
aqlyra-voice worker, actual provider credentials and a browser are required.
"""
import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config.settings import settings
from app.services import voice_session_service as voice


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "LIVEKIT_URL", "wss://voice.test.invalid")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "voice-test-key")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "voice-test-secret-do-not-use")
    monkeypatch.setattr(settings, "VOICE_AGENT_NAME", "aqlyra-voice")


def _jwt_claims(token: str) -> dict:
    parts = token.split(".")
    assert len(parts) == 3
    encoded = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded))


@pytest.mark.parametrize(
    "missing", ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
)
def test_missing_voice_provider_credentials_fail_closed(monkeypatch, missing):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, missing, "")

    with pytest.raises(voice.VoiceConfigurationError, match="not configured"):
        voice._require_voice_configuration()


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

    result = voice.create_voice_session(
        db=object(), user=user, mode="knowledge",
        conversation_id=str(conversation_id), title="Voice session",
        document_ids=documents,
    )
    claims = _jwt_claims(result.participant_token)
    grant = claims["video"]
    assert result.server_url == "wss://voice.test.invalid"
    assert result.mode == "knowledge"
    assert result.conversation_id == str(conversation_id)
    assert result.room_name.startswith(f"aqlyra-{conversation_id}-")
    assert grant["roomJoin"] is True
    assert grant["room"] == result.room_name
    assert grant["canSubscribe"] is True
    assert grant["canPublish"] is True
    assert claims["sub"].startswith(f"user-{owner_id}-")
    assert observed == {
        "resolved_owner": owner_id,
        "mode": "knowledge",
        "documents_owner": owner_id,
        "documents": documents,
    }

    metadata = json.loads(claims["metadata"])
    assert metadata == {
        "user_id": str(owner_id),
        "conversation_id": str(conversation_id),
        "mode": "knowledge",
        "document_ids": list(documents),
    }
    dispatches = claims["roomConfig"]["agents"]
    assert len(dispatches) == 1
    assert dispatches[0]["agentName"] == "aqlyra-voice"
    assert json.loads(dispatches[0]["metadata"]) == metadata
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
