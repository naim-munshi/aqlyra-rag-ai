"""Least-privilege worker role keeps common production safeguards.

Uses synthetic-only credentials. No external provider calls or migrations.
"""
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def production(role: str) -> dict:
    return {
        "APP_ENV": "production",
        "AQLYRA_PROCESS_ROLE": role,
        "SECRET_KEY": "ci-synthetic-not-a-real-password-or-secret-key-00001",
        "DATABASE_URL": (
            "postgresql+psycopg://ci:ci-only-long-fake-db-password"
            "@db.example.invalid:5432/aqlyra"
        ),
        "REDIS_URL": "rediss://cache.example.invalid:6379",
        "RATE_LIMIT_ENABLED": True,
        "RAG_GROUNDING_VERIFIER_ENABLED": True,
        "EMAIL_VERIFICATION_REQUIRED": True,
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": "ci-only-fake-groq",
        "EMBEDDING_PROVIDER": "huggingface",
        "HF_TOKEN": "ci-only-fake-hf",
        "DEBUG": False,
        # These fields are for HTTP authentication and CORS only.
        "GOOGLE_CLIENT_ID": "",
        "SMTP_FROM_EMAIL": "",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "CORS_ORIGINS": "http://localhost:3000",
    }


def test_production_worker_does_not_require_http_email_or_google_secrets():
    config = Settings(_env_file=None, **production("voice_worker"))
    assert config.APP_ENV == "production"
    assert config.AQLYRA_PROCESS_ROLE == "voice_worker"


def test_same_config_cannot_boot_public_production_api():
    with pytest.raises(ValidationError, match="SMTP_FROM_EMAIL|GOOGLE_CLIENT_ID"):
        Settings(_env_file=None, **production("api"))


@pytest.mark.parametrize("change", [
    {"SECRET_KEY": "weak"},
    {"DATABASE_URL": "postgresql://ci:weak@db.example.invalid/aqlyra"},
    {"RATE_LIMIT_ENABLED": False},
    {"RAG_GROUNDING_VERIFIER_ENABLED": False},
    {"EMAIL_VERIFICATION_REQUIRED": False},
    {"LLM_PROVIDER": "deterministic"},
    {"EMBEDDING_PROVIDER": "deterministic"},
    {"DEBUG": True},
])
def test_worker_must_keep_all_shared_production_guards(change):
    data = production("voice_worker")
    data.update(change)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **data)


def test_http_entrypoint_cannot_run_in_worker_role():
    code = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text()
    assert 'settings.AQLYRA_PROCESS_ROLE != "api"' in code
    image = (Path(__file__).resolve().parents[1] / "Dockerfile.voice").read_text()
    assert "ENV AQLYRA_PROCESS_ROLE=voice_worker" in image


def test_railway_one_gib_worker_never_prewarms_idle_livekit_children():
    """Guard against default production process pool near 1-GiB RSS limit."""
    text = (Path(__file__).resolve().parents[1] / "app" / "voice" / "worker.py").read_text()
    assert "AgentServer(num_idle_processes=0)" in text
    assert text.count("server = AgentServer(") == 1
