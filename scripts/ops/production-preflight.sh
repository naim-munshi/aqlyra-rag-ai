#!/usr/bin/env bash

set -uo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." \
  && pwd
)"

cd "$ROOT_DIR" || exit 1

ENV_FILE="${1:-backend/.env.production}"

PYTHON_BIN="${AQ_PYTHON_BIN:-}"

if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "PRODUCTION_PREFLIGHT=FAIL"
    echo "Python 3 interpreter not found"
    exit 1
  fi
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "PRODUCTION_PREFLIGHT=FAIL"
  echo "Production environment file not found"
  exit 1
fi

"$PYTHON_BIN" - "$ENV_FILE" <<'PY'
import sys
from pathlib import Path
from urllib.parse import (
    unquote,
    urlsplit,
)


env_path = Path(sys.argv[1])

values: dict[str, str] = {}

for raw_line in env_path.read_text(
    encoding="utf-8"
).splitlines():
    line = raw_line.strip()

    if (
        not line
        or line.startswith("#")
        or "=" not in line
    ):
        continue

    key, value = line.split("=", 1)

    values[key.strip()] = (
        value.strip()
        .strip('"')
        .strip("'")
    )


errors: list[str] = []


def require(key: str) -> str:
    value = values.get(key, "").strip()

    lowered = value.casefold()

    if (
        not value
        or "replace-with" in lowered
        or lowered in {
            "changeme",
            "change-me",
            "placeholder",
        }
    ):
        errors.append(
            f"{key} must be configured"
        )

    return value


if values.get("APP_ENV") != "production":
    errors.append(
        "APP_ENV must equal production"
    )


llm_provider = require(
    "LLM_PROVIDER"
).casefold()

require("LLM_MODEL")

if llm_provider not in {
    "groq",
    "openai",
}:
    errors.append(
        "LLM_PROVIDER must be groq or openai "
        "in production"
    )


grounding_enabled = values.get(
    "RAG_GROUNDING_VERIFIER_ENABLED",
    "",
).casefold()

if grounding_enabled not in {
    "true",
    "1",
    "yes",
    "on",
}:
    errors.append(
        "RAG_GROUNDING_VERIFIER_ENABLED "
        "must be true in production"
    )


llm_provider = require(
    "LLM_PROVIDER"
).casefold()

require("LLM_MODEL")

if llm_provider not in {
    "groq",
    "openai",
}:
    errors.append(
        "LLM_PROVIDER must be groq or openai "
        "in production"
    )


grounding_enabled = values.get(
    "RAG_GROUNDING_VERIFIER_ENABLED",
    "",
).casefold()

if grounding_enabled not in {
    "true",
    "1",
    "yes",
    "on",
}:
    errors.append(
        "RAG_GROUNDING_VERIFIER_ENABLED "
        "must be true in production"
    )

rate_limit_enabled = values.get(
    "RATE_LIMIT_ENABLED",
    "",
).casefold()

if rate_limit_enabled not in {
    "true",
    "1",
    "yes",
    "on",
}:
    errors.append(
        "RATE_LIMIT_ENABLED must be true "
        "in production"
    )


rate_limit_positive_keys = (
    "RATE_LIMIT_REDIS_TIMEOUT_SECONDS",
    "RATE_LIMIT_REGISTER_IP_LIMIT",
    "RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS",
    "RATE_LIMIT_LOGIN_IP_LIMIT",
    "RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS",
    "RATE_LIMIT_LOGIN_IDENTITY_LIMIT",
    "RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS",
    "RATE_LIMIT_UPLOAD_USER_LIMIT",
    "RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS",
    "RATE_LIMIT_PROCESS_USER_LIMIT",
    "RATE_LIMIT_PROCESS_USER_WINDOW_SECONDS",
    "RATE_LIMIT_RAG_USER_LIMIT",
    "RATE_LIMIT_RAG_USER_WINDOW_SECONDS",
    "RATE_LIMIT_CHAT_USER_LIMIT",
    "RATE_LIMIT_CHAT_USER_WINDOW_SECONDS",
    "RATE_LIMIT_VOICE_USER_LIMIT",
    "RATE_LIMIT_VOICE_USER_WINDOW_SECONDS",
)

for key in rate_limit_positive_keys:
    raw_value = require(key)

    try:
        parsed_value = float(raw_value)

        if parsed_value <= 0:
            raise ValueError

    except ValueError:
        errors.append(
            f"{key} must be positive"
        )


require(
    "RATE_LIMIT_CLIENT_IP_HEADER"
)


if values.get(
    "DEBUG",
    "",
).casefold() not in {
    "false",
    "0",
    "no",
}:
    errors.append(
        "DEBUG must be false"
    )


cors = require("CORS_ORIGINS")

lowered_cors = cors.casefold()

if (
    "*" in cors
    or "localhost" in lowered_cors
    or "127.0.0.1" in lowered_cors
):
    errors.append(
        "CORS_ORIGINS must contain only "
        "production origins"
    )


domain = require("APP_DOMAIN")
domain_lower = domain.casefold()

if (
    "://" in domain
    or "/" in domain
    or domain_lower == "localhost"
    or domain_lower == "example.com"
    or domain_lower.endswith(".example.com")
):
    errors.append(
        "APP_DOMAIN must be a real "
        "production hostname"
    )

if (
    domain
    and f"https://{domain}" not in cors
):
    errors.append(
        "CORS_ORIGINS must include "
        "https://APP_DOMAIN"
    )


caddy_email = require("CADDY_EMAIL")

if (
    "@" not in caddy_email
    or caddy_email.startswith("@")
    or caddy_email.endswith("@")
):
    errors.append(
        "CADDY_EMAIL must be a valid "
        "contact email"
    )


secret = require("SECRET_KEY")

if len(secret) < 32:
    errors.append(
        "SECRET_KEY must be at least "
        "32 characters"
    )


db_user = require("POSTGRES_USER")
db_password = require("POSTGRES_PASSWORD")
db_name = require("POSTGRES_DB")

if db_user.casefold() == "postgres":
    errors.append(
        "POSTGRES_USER must not use the "
        "default postgres account"
    )

if len(db_password) < 16:
    errors.append(
        "POSTGRES_PASSWORD must be at least "
        "16 characters"
    )


docker_url = require(
    "DATABASE_URL_DOCKER"
)

try:
    parsed = urlsplit(docker_url)

    url_user = unquote(
        parsed.username or ""
    )
    url_password = unquote(
        parsed.password or ""
    )
    url_db = parsed.path.lstrip("/")

    if (
        parsed.scheme
        != "postgresql+psycopg"
    ):
        errors.append(
            "DATABASE_URL_DOCKER must use "
            "postgresql+psycopg"
        )

    if parsed.hostname != "postgres":
        errors.append(
            "DATABASE_URL_DOCKER host must "
            "be postgres"
        )

    if url_user != db_user:
        errors.append(
            "DATABASE_URL_DOCKER user does "
            "not match POSTGRES_USER"
        )

    if url_password != db_password:
        errors.append(
            "DATABASE_URL_DOCKER password "
            "does not match POSTGRES_PASSWORD"
        )

    if url_db != db_name:
        errors.append(
            "DATABASE_URL_DOCKER database "
            "does not match POSTGRES_DB"
        )

except Exception:
    errors.append(
        "DATABASE_URL_DOCKER is invalid"
    )


redis_url = require(
    "REDIS_URL_DOCKER"
)

try:
    parsed_redis = urlsplit(
        redis_url
    )

    if parsed_redis.scheme not in {
        "redis",
        "rediss",
    }:
        errors.append(
            "REDIS_URL_DOCKER must use "
            "redis or rediss"
        )

    if parsed_redis.hostname != "redis":
        errors.append(
            "REDIS_URL_DOCKER host must be redis"
        )

except Exception:
    errors.append(
        "REDIS_URL_DOCKER is invalid"
    )


if llm_provider == "groq":
    require("GROQ_API_KEY")

elif llm_provider == "openai":
    require("OPENAI_API_KEY")


for key in (
    "HF_TOKEN",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
):
    require(key)


if errors:
    print("PRODUCTION_PREFLIGHT=FAIL")

    for error in errors:
        print(f"- {error}")

    raise SystemExit(1)


print("APP_ENV=PASS")
print("DEBUG=PASS")
print("CORS=PASS")
print("APP_DOMAIN=PASS")
print("CADDY_EMAIL=PASS")
print("SECRET_KEY=PASS")
print("POSTGRES_CREDENTIALS=PASS")
print("DATABASE_URL_DOCKER=PASS")
print("LLM_PROVIDER=PASS")
print("RAG_GROUNDING_VERIFIER=PASS")
print("RATE_LIMITING=PASS")
print("REDIS_RATE_LIMIT_BACKEND=PASS")
print("LLM_API_KEY=SET")
print("HF_TOKEN=SET")
print("LIVEKIT_CONFIG=SET")
print("PRODUCTION_PREFLIGHT=PASS")
PY
