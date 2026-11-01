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
    "VOICE_STT_PROVIDER",
    "VOICE_STT_MODEL",
    "VOICE_STT_LANGUAGE",
    "VOICE_SESSION_LLM_PROVIDER",
    "VOICE_SESSION_LLM_MODEL",
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
    if values["LLM_PROVIDER"].strip().lower() not in {"groq", "openai"}:
        raise VoiceWorkerPreflightError("Unsupported Aqlyra brain provider")
    stt_provider = values["VOICE_STT_PROVIDER"].strip().lower()
    session_provider = values["VOICE_SESSION_LLM_PROVIDER"].strip().lower()
    if stt_provider not in {"livekit", "groq"}:
        raise VoiceWorkerPreflightError("Unsupported speech provider")
    if session_provider not in {"livekit", "groq"}:
        raise VoiceWorkerPreflightError("Unsupported session model provider")
    if stt_provider == "livekit":
        if not values["VOICE_STT_MODEL"].strip().startswith("deepgram/"):
            raise VoiceWorkerPreflightError("Configured STT is not a LiveKit Deepgram model")
    elif "/" in values["VOICE_STT_MODEL"].strip():
        raise VoiceWorkerPreflightError("Groq STT requires a Groq model ID")
    if session_provider == "livekit" and "/" not in values["VOICE_SESSION_LLM_MODEL"].strip():
        raise VoiceWorkerPreflightError("LiveKit session LLM requires a provider/model ID")
    if (
        stt_provider == "groq" or session_provider == "groq"
        or values["LLM_PROVIDER"].strip().lower() == "groq"
    ) and not values.get("GROQ_API_KEY", "").strip():
        raise VoiceWorkerPreflightError("GROQ_API_KEY required for selected provider")
    if values["EMBEDDING_PROVIDER"].strip().lower() == "deterministic":
        raise VoiceWorkerPreflightError("Real embeddings are required")
    if values["EMBEDDING_PROVIDER"].strip().lower() == "remote_onnx":
        required_remote = (
            "REMOTE_SEMANTIC_URL", "REMOTE_SEMANTIC_TOKEN",
            "EMBEDDING_MODEL", "EMBEDDING_DIMENSION",
        )
        absent = [key for key in required_remote if not values.get(key, "").strip()]
        if absent:
            raise VoiceWorkerPreflightError(
                "Missing remote semantic configuration keys: " + ", ".join(absent)
            )
        if (values["EMBEDDING_MODEL"].strip()
                != "bekko-static-multilingual-int8-mrl384-v1"
                or values["EMBEDDING_DIMENSION"].strip() != "384"):
            raise VoiceWorkerPreflightError(
                "Remote semantic model identity/dimension must match production"
            )
        if len(values["REMOTE_SEMANTIC_TOKEN"].strip()) < 32:
            raise VoiceWorkerPreflightError("REMOTE_SEMANTIC_TOKEN is too short")
        try:
            remote = urlsplit(values["REMOTE_SEMANTIC_URL"].strip())
            if (remote.scheme != "https"
                    or remote.hostname != "aqlyra-semantic-worker.onrender.com"
                    or remote.port not in (None, 443)
                    or remote.path not in ("", "/")
                    or remote.username is not None
                    or remote.password is not None
                    or remote.query or remote.fragment):
                raise ValueError
        except (ValueError, TypeError):
            raise VoiceWorkerPreflightError(
                "REMOTE_SEMANTIC_URL must identify the existing trusted HTTPS worker"
            ) from None
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
