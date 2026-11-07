"""Trust-boundary regression tests for LiveKit job dispatch metadata."""
import json
from uuid import uuid4

import pytest

from app.voice.job_metadata import (
    MAX_VOICE_DOCUMENTS,
    MAX_VOICE_JOB_BYTES,
    VoiceJobData,
)


def _message(**changes):
    payload = {
        "user_id": str(uuid4()),
        "conversation_id": str(uuid4()),
        "mode": "knowledge",
        "document_ids": [str(uuid4()), str(uuid4())],
    }
    payload.update(changes)
    return payload


def test_canonical_real_backend_dispatch_metadata_round_trip():
    payload = _message()
    parsed = VoiceJobData.from_metadata(json.dumps(payload))
    assert parsed.user_id == payload["user_id"]
    assert parsed.conversation_id == payload["conversation_id"]
    assert parsed.mode == "knowledge"
    assert parsed.document_ids == tuple(payload["document_ids"])


@pytest.mark.parametrize("change", [
    {"user_id": "../owner"},
    {"user_id": str(uuid4()).upper()},
    {"user_id": 123},
    {"conversation_id": "not-an-id"},
    {"conversation_id": None},
    {"mode": "admin"},
    {"mode": 1},
    {"document_ids": ["../../foreign"]},
    {"document_ids": ["a"]},
    {"document_ids": [123]},
    {"document_ids": str(uuid4())},
    {"document_ids": [str(uuid4()) for _ in range(MAX_VOICE_DOCUMENTS + 1)]},
])
def test_invalid_dispatch_identity_or_scope_fails_closed(change):
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata(json.dumps(_message(**change)))


def test_duplicate_documents_and_json_keys_are_rejected():
    duplicate = str(uuid4())
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata(json.dumps(_message(document_ids=[
            duplicate, duplicate,
        ])))
    payload = _message()
    repeated = json.dumps(payload)[:-1] + ',"user_id":"another-owner"}'
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata(repeated)


def test_explicit_payload_schema_prevents_unexpected_fields():
    payload = _message()
    payload["extra"] = "not-approved"
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata(json.dumps(payload))
    payload.pop("extra")
    payload.pop("document_ids")
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata(json.dumps(payload))
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata("[]")


def test_oversized_metadata_and_nonstring_values_rejected():
    with pytest.raises(ValueError):
        VoiceJobData.from_metadata("x" * (MAX_VOICE_JOB_BYTES + 1))
    for raw in (None, 123, "", "null", "{", "[1,2]", "true"):
        with pytest.raises(ValueError):
            VoiceJobData.from_metadata(raw)


def test_valid_normal_session_accepts_empty_document_scope():
    payload = _message(mode="normal", document_ids=[])
    result = VoiceJobData.from_metadata(json.dumps(payload))
    assert result.document_ids == ()
