"""Database pool settings are bounded and preserve existing defaults."""
import pytest
from pydantic import ValidationError

from app.config.settings import Settings, settings
from app.database.connection import connection_pool_kwargs


def test_existing_pool_defaults_unchanged():
    cfg = Settings(_env_file=None)
    assert cfg.DATABASE_POOL_SIZE == 5
    assert cfg.DATABASE_MAX_OVERFLOW == 10
    assert cfg.DATABASE_POOL_TIMEOUT_SECONDS == 30
    assert cfg.DATABASE_POOL_RECYCLE_SECONDS == 1800


def test_engine_receives_configured_bounded_pool_options():
    opts = connection_pool_kwargs()
    assert opts == {
        "pool_pre_ping": True,
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT_SECONDS,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE_SECONDS,
    }


@pytest.mark.parametrize("overrides", [
    {"DATABASE_POOL_SIZE": 0},
    {"DATABASE_POOL_SIZE": 33},
    {"DATABASE_MAX_OVERFLOW": -1},
    {"DATABASE_MAX_OVERFLOW": 33},
    {"DATABASE_POOL_TIMEOUT_SECONDS": 0},
    {"DATABASE_POOL_TIMEOUT_SECONDS": 61},
    {"DATABASE_POOL_RECYCLE_SECONDS": 59},
    {"DATABASE_POOL_RECYCLE_SECONDS": 7201},
])
def test_unsafe_pool_configuration_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_neon_sized_pool_is_valid():
    cfg = Settings(
        _env_file=None,
        DATABASE_POOL_SIZE=2,
        DATABASE_MAX_OVERFLOW=1,
        DATABASE_POOL_TIMEOUT_SECONDS=10,
        DATABASE_POOL_RECYCLE_SECONDS=300,
    )
    assert cfg.DATABASE_POOL_SIZE + cfg.DATABASE_MAX_OVERFLOW == 3
