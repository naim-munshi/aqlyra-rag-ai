"""Neon libpq URLs must use Aqlyra's installed psycopg v3 driver.

This test contains only synthetic connection strings. It makes no network
requests and does not modify a database.
"""

from sqlalchemy.engine import make_url

from app.config.settings import Settings


def make_settings(url: str) -> Settings:
    return Settings(
        SECRET_KEY="synthetic-test-only-" + "x" * 40,
        DATABASE_URL=url,
        APP_ENV="development",
        EMBEDDING_PROVIDER="deterministic",
        LLM_PROVIDER="deterministic",
        RATE_LIMIT_ENABLED=False,
        EMAIL_VERIFICATION_REQUIRED=False,
    )


def test_neon_libpq_url_selects_installed_psycopg_v3():
    original = (
        "postgresql://appuser:synthetic-p%40ssword@"
        "ep-example-pooler.ap-southeast-1.aws.neon.tech/"
        "neondb?sslmode=require"
    )
    normalized = make_settings(original).DATABASE_URL
    assert normalized == (
        "postgresql+psycopg://" + original[len("postgresql://"):]
    )
    parsed = make_url(normalized)
    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.query["sslmode"] == "require"
    assert parsed.password == "synthetic-p@ssword"


def test_explicit_psycopg_v3_url_is_preserved_verbatim():
    original = "postgresql+psycopg://user:synthetic@db.example.invalid/test"
    assert make_settings(original).DATABASE_URL == original


def test_unrelated_dialect_url_is_not_rewritten():
    original = "sqlite:///local-synthetic-test.db"
    assert make_settings(original).DATABASE_URL == original
