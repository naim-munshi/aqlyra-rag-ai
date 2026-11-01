"""Fail-closed, secret-safe preflight for the dedicated LiveKit voice worker.

This checks configuration *only*. It does not claim that the worker registered
or that STT/TTS can answer a real call. No credentials or URLs are logged.
"""
from __future__ import annotations

import ipaddress
import os
import re
import sys
from collections.abc import Mapping
from urllib.parse import urlsplit

REQUIRED = (
    "APP_ENV",
    "AQLYRA_PROCESS_ROLE",
    "RATE_LIMIT_ENABLED",
    "RAG_GROUNDING_VERIFIER_ENABLED",
    "LLM_PROVIDER",
    "EMBEDDING_PROVIDER",
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "VOICE_AGENT_NAME",
    "GROQ_API_KEY",
    "VOICE_STT_MODEL",
    "VOICE_TTS_MODEL",
    "VOICE_TTS_VOICE",
)


class VoiceWorkerPreflightError(RuntimeError):
    """Safe-to-display error; never contain secret values."""


def validate_voice_worker_environment(values: Mapping[str, str]) -> None:
    missing = sorted(key for key in REQUIRED if not values.get(key, "").strip())
    if missing:
        raise VoiceWorkerPreflightError(
            "Missing voice worker configuration keys: " + ", ".join(missing)
        )

    if values["APP_ENV"].strip().lower() != "production":
        raise VoiceWorkerPreflightError(
            "APP_ENV must be production for the deployed voice worker"
        )

    if values["AQLYRA_PROCESS_ROLE"].strip() != "voice_worker":
        raise VoiceWorkerPreflightError("AQLYRA_PROCESS_ROLE must be voice_worker")
    if values["RATE_LIMIT_ENABLED"].strip().lower() != "true":
        raise VoiceWorkerPreflightError("Production rate limiting must be enabled")
    if values["RAG_GROUNDING_VERIFIER_ENABLED"].strip().lower() != "true":
        raise VoiceWorkerPreflightError("Production grounding must be enabled")
    if values["LLM_PROVIDER"].strip().lower() == "deterministic":
        raise VoiceWorkerPreflightError("A real LLM provider is required")
    if values["EMBEDDING_PROVIDER"].strip().lower() == "deterministic":
        raise VoiceWorkerPreflightError("Real embeddings are required")
    if (
        values["EMBEDDING_PROVIDER"].strip().lower() == "huggingface"
        and not values.get("HF_TOKEN", "").strip()
    ):
        raise VoiceWorkerPreflightError("HF_TOKEN is required for Hugging Face")
    if (
        "openai" in (
            values["LLM_PROVIDER"].strip().lower(),
            values["EMBEDDING_PROVIDER"].strip().lower(),
        )
        and not values.get("OPENAI_API_KEY", "").strip()
    ):
        raise VoiceWorkerPreflightError("OPENAI_API_KEY is required for OpenAI")

    if len(values["SECRET_KEY"].strip()) < 32:
        raise VoiceWorkerPreflightError("SECRET_KEY must be at least 32 characters")

    try:
        livekit = urlsplit(values["LIVEKIT_URL"].strip())
        host = livekit.hostname
        normalized = host.lower().rstrip(".") if host else ""
        if (
            livekit.scheme != "wss"
            or not host
            or normalized != host.lower()
            or livekit.username is not None
            or livekit.password is not None
            or livekit.query
            or livekit.fragment
            or livekit.path not in ("", "/")
            or (livekit.port is not None and livekit.port < 1)
        ):
            raise ValueError
        if normalized in {"localhost"} or normalized.endswith(
            (".localhost", ".local", ".internal")
        ):
            raise ValueError
        try:
            ip = ipaddress.ip_address(normalized)
        except ValueError:
            # Non-IP DNS host: require a public FQDN, not a single-label name.
            if "." not in normalized:
                raise ValueError from None
        else:
            if not ip.is_global:
                raise ValueError
    except (ValueError, TypeError):
        raise VoiceWorkerPreflightError(
            "LIVEKIT_URL must be a public wss endpoint with no path or secrets"
        ) from None

    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", values["VOICE_AGENT_NAME"].strip()):
        raise VoiceWorkerPreflightError("VOICE_AGENT_NAME is invalid")

    try:
        db = urlsplit(values["DATABASE_URL"].strip())
        if db.scheme not in {"postgresql", "postgresql+psycopg", "postgres"} or not db.hostname:
            raise ValueError
    except ValueError:
        raise VoiceWorkerPreflightError("DATABASE_URL must use PostgreSQL") from None

    try:
        redis = urlsplit(values["REDIS_URL"].strip())
        if redis.scheme not in {"redis", "rediss"} or not redis.hostname:
            raise ValueError
    except ValueError:
        raise VoiceWorkerPreflightError("REDIS_URL must use Redis") from None


def main() -> int:
    try:
        validate_voice_worker_environment(os.environ)
    except VoiceWorkerPreflightError as exc:
        print("voice_worker_preflight=BLOCKED: " + str(exc), file=sys.stderr)
        return 1
    print("voice_worker_preflight=PASS (configuration only, not live audio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
