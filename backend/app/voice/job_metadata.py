"""Strict LiveKit-dispatched Aqlyra voice job metadata contract.

Validate the metadata boundary before starting an STT/RAG/TTS session.
Authoritative conversation/document ownership is rechecked via PostgreSQL
by the worker; this parser never grants permission to access anything.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import UUID

MAX_VOICE_JOB_BYTES = 8192
MAX_VOICE_DOCUMENTS = 50
_FIELDS = frozenset({"user_id", "conversation_id", "mode", "document_ids"})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate voice metadata key")
        obj[key] = value
    return obj


def _canonical_uuid(value: object) -> str:
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError("Invalid voice identity")
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid voice identity") from exc
    if str(parsed) != value:
        raise ValueError("Invalid voice identity")
    return value


@dataclass(frozen=True, slots=True)
class VoiceJobData:
    user_id: str
    conversation_id: str
    mode: str
    document_ids: tuple[str, ...]

    @classmethod
    def from_metadata(cls, metadata: str) -> "VoiceJobData":
        if (
            not isinstance(metadata, str)
            or len(metadata.encode("utf-8")) > MAX_VOICE_JOB_BYTES
        ):
            raise ValueError("Invalid voice job metadata")
        try:
            payload = json.loads(
                metadata,
                object_pairs_hook=_unique_pairs,
            )
        except (ValueError, UnicodeError, TypeError) as exc:
            raise ValueError("Invalid voice job metadata") from exc
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise ValueError("Invalid voice job metadata")
        if payload["mode"] not in ("normal", "knowledge"):
            raise ValueError("Invalid voice job mode")
        raw_ids = payload["document_ids"]
        if not isinstance(raw_ids, list) or len(raw_ids) > MAX_VOICE_DOCUMENTS:
            raise ValueError("Invalid voice document scope")
        ids = tuple(_canonical_uuid(value) for value in raw_ids)
        if len(set(ids)) != len(ids):
            raise ValueError("Invalid voice document scope")
        return cls(
            user_id=_canonical_uuid(payload["user_id"]),
            conversation_id=_canonical_uuid(payload["conversation_id"]),
            mode=payload["mode"],
            document_ids=ids,
        )
