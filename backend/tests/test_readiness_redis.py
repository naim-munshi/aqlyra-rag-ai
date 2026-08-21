from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.api.v1 import health as health_api


class HealthyRedis:
    def ping(
        self,
    ) -> bool:
        return True


class UnavailableRedis:
    def ping(
        self,
    ) -> bool:
        raise RedisError(
            "simulated redis outage"
        )


def test_readiness_checks_redis_when_rate_limiting_enabled(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_api.settings,
        "RATE_LIMIT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        health_api,
        "get_rate_limit_redis",
        lambda: HealthyRedis(),
    )

    response = client.get(
        "/api/v1/readiness"
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "checks"
        ][
            "redis"
        ]
        == "ready"
    )


def test_readiness_fails_when_required_redis_is_down(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_api.settings,
        "RATE_LIMIT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        health_api,
        "get_rate_limit_redis",
        lambda: UnavailableRedis(),
    )

    response = client.get(
        "/api/v1/readiness"
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Service dependencies "
            "are unavailable"
        ),
    }


def test_readiness_does_not_require_redis_when_limiter_disabled(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_api.settings,
        "RATE_LIMIT_ENABLED",
        False,
    )

    def must_not_be_called():
        raise AssertionError(
            "Redis should not be checked"
        )

    monkeypatch.setattr(
        health_api,
        "get_rate_limit_redis",
        must_not_be_called,
    )

    response = client.get(
        "/api/v1/readiness"
    )

    assert response.status_code == 200

    assert (
        "redis"
        not in response.json()[
            "checks"
        ]
    )
