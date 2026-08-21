import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def _production_settings(
    monkeypatch,
    database_url: str,
) -> Settings:
    monkeypatch.setenv(
        "APP_ENV",
        "production",
    )
    monkeypatch.setenv(
        "DEBUG",
        "false",
    )
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://app.aqlyra.example",
    )
    monkeypatch.setenv(
        "SECRET_KEY",
        "aqlyra-production-test-secret-"
        "0123456789abcdef",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        database_url,
    )
    monkeypatch.setenv(
        "RAG_GROUNDING_VERIFIER_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "groq",
    )
    monkeypatch.setenv(
        "GROQ_API_KEY",
        "test-only-groq-key",
    )
    monkeypatch.setenv(
        "RATE_LIMIT_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "REDIS_URL",
        "redis://redis:6379/0",
    )

    return Settings(
        _env_file=None,
    )


def test_production_rejects_default_database_password(
    monkeypatch,
) -> None:
    with pytest.raises(
        ValidationError,
        match="Production DATABASE_URL",
    ):
        _production_settings(
            monkeypatch,
            (
                "postgresql+psycopg://"
                "postgres:postgres@"
                "postgres:5432/"
                "aqlyra_rag_ai"
            ),
        )


def test_production_rejects_short_database_password(
    monkeypatch,
) -> None:
    with pytest.raises(
        ValidationError,
        match="Production DATABASE_URL",
    ):
        _production_settings(
            monkeypatch,
            (
                "postgresql+psycopg://"
                "aqlyra:shortpass@"
                "postgres:5432/"
                "aqlyra_rag_ai"
            ),
        )


def test_production_accepts_strong_database_password(
    monkeypatch,
) -> None:
    settings = _production_settings(
        monkeypatch,
        (
            "postgresql+psycopg://"
            "aqlyra:"
            "strong-production-db-secret-1234@"
            "postgres:5432/"
            "aqlyra_rag_ai"
        ),
    )

    assert settings.is_production is True
