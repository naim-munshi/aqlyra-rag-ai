#!/usr/bin/env python3
"""Offline owner-only LiveKit secrets preflight: never prints secret values.

No network calls, provider changes, secret uploads, or LiveKit deployment.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import parse_qs, urlsplit

REQUIRED = frozenset({
    "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "GROQ_API_KEY",
    "HF_TOKEN", "GOOGLE_CLIENT_ID", "RESEND_API_KEY", "SMTP_FROM_EMAIL",
    "EMAIL_DELIVERY_PROVIDER", "LLM_PROVIDER", "EMBEDDING_PROVIDER",
    "RAG_GROUNDING_VERIFIER_ENABLED", "RATE_LIMIT_ENABLED", "CORS_ORIGINS",
    "APP_ENV", "DEBUG", "VOICE_AGENT_NAME",
})
AUTO_INJECTED = frozenset({
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
})
KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
PLACEHOLDER = re.compile(
    r"^(?:<.*>|\*+|change[-_ ]?me|replace[-_ ]?me|your[-_ ].*|"
    r"dummy|placeholder|example|test[-_ ].*|TODO)$",
    re.IGNORECASE,
)


class VoicePreflightBlocked(ValueError):
    """Caller-visible diagnostics must never embed configuration values."""


def load_secrets(path: Path) -> dict[str, str]:
    # Never allow even mode-600 secrets to be left inside the Git worktree.
    # Resolve parent paths as well, so symlinked directories cannot bypass.
    repo_root = Path(__file__).resolve().parents[2]
    if path.resolve().is_relative_to(repo_root):
        raise VoicePreflightBlocked("secrets must be outside the Git repository")
    if path.is_symlink():
        raise VoicePreflightBlocked("secret file symlink denied")
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_mode & 0o077
        or (hasattr(os, "getuid") and info.st_uid != os.getuid())
        or not 0 < info.st_size <= 65536
    ):
        raise VoicePreflightBlocked("secret file ownership/mode/size invalid")
    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export ") or "=" not in line:
                raise VoicePreflightBlocked("only bare key-value lines accepted")
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not KEY.fullmatch(key) or key in values:
                raise VoicePreflightBlocked("invalid or duplicate key")
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise VoicePreflightBlocked("invalid quoted value")
                value = value[1:-1]
            if (
                not value.strip()
                or "\x00" in value
                or "\r" in value
                or "\n" in value
                or PLACEHOLDER.fullmatch(value.strip())
                or (chr(36) + "{") in value
                or (chr(36) + "(") in value
            ):
                raise VoicePreflightBlocked("empty/placeholder/expansion value")
            values[key] = value
    return values


def approved_url(value: str, *, redis: bool) -> bool:
    try:
        raw = value
        if not redis and raw.startswith("postgresql+psycopg://"):
            raw = "postgresql://" + raw[len("postgresql+psycopg://"):]
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        query = parse_qs(parsed.query)
        if (
            not host or parsed.fragment
            or set(query) & {"host", "hostaddr", "service", "dbname", "port", "user"}
            or any(len(items) != 1 for items in query.values())
        ):
            return False
        if redis:
            return (
                parsed.scheme == "rediss"
                and host.endswith(".upstash.io")
                and bool(parsed.password)
                and parsed.port in (None, 6379)
            )
        return (
            parsed.scheme == "postgresql"
            and host.endswith(".neon.tech")
            and bool(parsed.username) and bool(parsed.password)
            and len(parsed.path) > 1
            and parsed.port in (None, 5432)
            and query.get("sslmode") in (["require"], ["verify-full"])
        )
    except (TypeError, ValueError, AttributeError):
        return False


def validate(values: dict[str, str]) -> None:
    if AUTO_INJECTED & values.keys():
        raise VoicePreflightBlocked("LiveKit-managed keys must not be uploaded")
    missing = REQUIRED - values.keys()
    if missing:
        # Only key names, never values.
        raise VoicePreflightBlocked("missing mandatory key names")
    if len(values["SECRET_KEY"]) < 32:
        raise VoicePreflightBlocked("SECRET_KEY insufficient length")
    if not approved_url(values["DATABASE_URL"], redis=False):
        raise VoicePreflightBlocked("DATABASE_URL must be approved TLS Neon")
    if not approved_url(values["REDIS_URL"], redis=True):
        raise VoicePreflightBlocked("REDIS_URL must be approved TLS Upstash")
    expected = {
        "EMAIL_DELIVERY_PROVIDER": "resend",
        "LLM_PROVIDER": "groq",
        "EMBEDDING_PROVIDER": "huggingface",
        "RAG_GROUNDING_VERIFIER_ENABLED": "true",
        "RATE_LIMIT_ENABLED": "true",
        "APP_ENV": "production",
        "DEBUG": "false",
        "VOICE_AGENT_NAME": "aqlyra-voice",
        "CORS_ORIGINS": "https://aqlyra-navy.vercel.app",
    }
    for name, approved in expected.items():
        if values[name] != approved:
            raise VoicePreflightBlocked("production-safe configuration mismatch")
    if values["SMTP_FROM_EMAIL"].count("@") != 1:
        raise VoicePreflightBlocked("SMTP_FROM_EMAIL invalid")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        validate(load_secrets(args.secrets_file))
    except (OSError, UnicodeError, VoicePreflightBlocked):
        print("LIVEKIT_SECRETS_PREFLIGHT=BLOCKED", file=sys.stderr)
        return 2
    print("LIVEKIT_SECRETS_PREFLIGHT=PASS")
    print("LIVEKIT_DEPLOYMENT=NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
