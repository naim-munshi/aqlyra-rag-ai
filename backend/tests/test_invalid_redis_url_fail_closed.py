"""Live Redis misconfiguration must never weaken rate limiting.

The synthetic REST-style URL is deliberately invalid for redis-py.
No network requests or secrets are used in this test.
"""
from fastapi import HTTPException
import pytest

from app.config.settings import settings
from app.core.rate_limit import enforce_rate_limit, get_rate_limit_redis


@pytest.fixture
def invalid_redis_settings(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "https://upstash-rest.invalid")
    get_rate_limit_redis.cache_clear()
    yield
    get_rate_limit_redis.cache_clear()


def test_invalid_redis_scheme_fails_closed_at_rate_limit(invalid_redis_settings):
    with pytest.raises(HTTPException) as result:
        enforce_rate_limit(
            bucket="test-redis-misconfiguration",
            identity="synthetic-subject",
            limit=1,
            window_seconds=60,
        )
    assert result.value.status_code == 503
    assert "unavailable" in result.value.detail


def test_invalid_redis_scheme_gives_503_not_500_at_readiness(
    client, invalid_redis_settings,
):
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service dependencies are unavailable"}
