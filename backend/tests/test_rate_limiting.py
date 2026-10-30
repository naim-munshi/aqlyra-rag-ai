from io import BytesIO

from redis.exceptions import RedisError

import app.core.rate_limit as rate_limit
from app.config.settings import settings


PASSWORD = "RateLimitPass123!"


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def eval(
        self,
        script,
        number_of_keys,
        key,
        window_seconds,
    ):
        del script
        del number_of_keys

        current = (
            self.counts.get(
                key,
                0,
            )
            + 1
        )

        self.counts[key] = current

        return [
            current,
            int(window_seconds),
        ]


class BrokenRedis:
    def eval(
        self,
        *args,
        **kwargs,
    ):
        del args
        del kwargs

        raise RedisError(
            "simulated redis outage"
        )


def configure(
    monkeypatch,
    redis_client,
) -> None:
    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_REGISTER_IP_LIMIT",
        100,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS",
        60,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_LOGIN_IP_LIMIT",
        100,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS",
        60,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_LOGIN_IDENTITY_LIMIT",
        100,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS",
        60,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_UPLOAD_USER_LIMIT",
        100,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS",
        60,
    )

    monkeypatch.setattr(
        rate_limit,
        "get_rate_limit_redis",
        lambda: redis_client,
    )


def register(
    client,
    suffix: str,
):
    return client.post(
        "/api/v1/auth/register",
        json={
            "username": suffix,
            "email": (
                f"{suffix}@example.com"
            ),
            "password": PASSWORD,
        },
        headers={
            "X-Aqlyra-Client-IP":
                "198.51.100.10",
        },
    )


def login(
    client,
    suffix: str,
    password: str = PASSWORD,
):
    return client.post(
        "/api/v1/auth/login",
        json={
            "email": (
                f"{suffix}@example.com"
            ),
            "password": password,
        },
        headers={
            "X-Aqlyra-Client-IP":
                "198.51.100.10",
        },
    )


def auth_headers(
    client,
    suffix: str,
) -> dict[str, str]:
    created = register(
        client,
        suffix,
    )

    assert created.status_code == 201

    authenticated = login(
        client,
        suffix,
    )

    assert (
        authenticated.status_code
        == 200
    )

    return {
        "Authorization": (
            "Bearer "
            + authenticated.json()[
                "access_token"
            ]
        )
    }


def test_register_ip_limit_returns_429_with_retry_after(
    client,
    monkeypatch,
) -> None:
    fake = FakeRedis()

    configure(
        monkeypatch,
        fake,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_REGISTER_IP_LIMIT",
        2,
    )

    assert (
        register(
            client,
            "rate-register-1",
        ).status_code
        == 201
    )

    assert (
        register(
            client,
            "rate-register-2",
        ).status_code
        == 201
    )

    blocked = register(
        client,
        "rate-register-3",
    )

    assert blocked.status_code == 429

    assert (
        int(
            blocked.headers[
                "retry-after"
            ]
        )
        >= 1
    )


def test_login_identity_bucket_counts_failed_passwords_only(
    client,
    monkeypatch,
) -> None:
    fake = FakeRedis()

    configure(
        monkeypatch,
        fake,
    )

    suffix = "rate-login-user"

    assert (
        register(
            client,
            suffix,
        ).status_code
        == 201
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_LOGIN_IDENTITY_LIMIT",
        2,
    )

    successful = login(
        client,
        suffix,
    )

    assert successful.status_code == 200

    first = login(
        client,
        suffix,
        "WrongPassword1!",
    )

    second = login(
        client,
        suffix,
        "WrongPassword2!",
    )

    third = login(
        client,
        suffix,
        "WrongPassword3!",
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429

    assert (
        "retry-after"
        in third.headers
    )


def test_upload_bucket_is_isolated_per_user(
    client,
    monkeypatch,
) -> None:
    fake = FakeRedis()

    configure(
        monkeypatch,
        fake,
    )

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_UPLOAD_USER_LIMIT",
        1,
    )

    first_headers = auth_headers(
        client,
        "rate-upload-one",
    )

    second_headers = auth_headers(
        client,
        "rate-upload-two",
    )

    first = client.post(
        "/api/v1/documents/upload",
        headers=first_headers,
        files={
            "file": (
                "one.md",
                BytesIO(b"first unique file"),
                "text/markdown",
            )
        },
    )

    blocked = client.post(
        "/api/v1/documents/upload",
        headers=first_headers,
        files={
            "file": (
                "two.md",
                BytesIO(b"second unique file"),
                "text/markdown",
            )
        },
    )

    isolated = client.post(
        "/api/v1/documents/upload",
        headers=second_headers,
        files={
            "file": (
                "three.md",
                BytesIO(b"third unique file"),
                "text/markdown",
            )
        },
    )

    assert first.status_code == 201
    assert blocked.status_code == 429
    assert isolated.status_code == 201


def test_redis_failure_fails_closed_with_503(
    client,
    monkeypatch,
) -> None:
    configure(
        monkeypatch,
        BrokenRedis(),
    )

    response = register(
        client,
        "rate-redis-down",
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "Rate limiting service "
        "is unavailable"
    )


def test_disabled_limiter_does_not_touch_redis(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_ENABLED",
        False,
    )

    monkeypatch.setattr(
        rate_limit,
        "get_rate_limit_redis",
        lambda: BrokenRedis(),
    )

    response = register(
        client,
        "rate-disabled",
    )

    assert response.status_code == 201


def test_retrieval_search_is_rate_limited(
    client,
    monkeypatch,
) -> None:
    fake = FakeRedis()
    configure(monkeypatch, fake)
    headers = auth_headers(client, "rate-retrieval")

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_RAG_USER_LIMIT",
        1,
    )

    first = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={"query": "private document search"},
    )
    second = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={"query": "another search"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert "retry-after" in second.headers


def test_embedding_rebuild_is_rate_limited(
    client,
    monkeypatch,
) -> None:
    fake = FakeRedis()
    configure(monkeypatch, fake)
    headers = auth_headers(client, "rate-reindex")

    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_PROCESS_USER_LIMIT",
        1,
    )

    endpoint = (
        "/api/v1/documents/"
        "00000000-0000-0000-0000-000000000000"
        "/embeddings/rebuild"
    )

    first = client.post(endpoint, headers=headers)
    second = client.post(endpoint, headers=headers)

    assert first.status_code == 404
    assert second.status_code == 429
    assert "retry-after" in second.headers


def _proxy_ip_request(peer: str, forged_ip: str):
    from starlette.requests import Request

    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "path": "/api/v1/auth/login",
        "query_string": b"",
        "headers": [
            (b"x-aqlyra-client-ip", forged_ip.encode("ascii")),
            (b"x-forwarded-for", b"192.0.2.1"),
        ],
        "client": (peer, 54321),
        "server": ("aqlyra-api", 443),
    })


def test_public_production_ingress_ignores_spoofed_client_ip(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(
        settings, "RATE_LIMIT_TRUSTED_PROXY_SOURCE_IPS", "",
    )
    request = _proxy_ip_request("198.51.100.19", "203.0.113.234")
    assert rate_limit._resolve_client_ip(request) == "198.51.100.19"


def test_production_only_trusts_header_from_explicit_direct_proxy(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(
        settings, "RATE_LIMIT_TRUSTED_PROXY_SOURCE_IPS",
        "10.10.20.1, 2001:db8::3",
    )
    direct_proxy = _proxy_ip_request("10.10.20.1", "203.0.113.234")
    untrusted = _proxy_ip_request("198.51.100.19", "203.0.113.234")
    assert rate_limit._resolve_client_ip(direct_proxy) == "203.0.113.234"
    assert rate_limit._resolve_client_ip(untrusted) == "198.51.100.19"


def test_invalid_proxy_allowlist_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(
        settings, "RATE_LIMIT_TRUSTED_PROXY_SOURCE_IPS",
        "0.0.0.0/0",
    )
    request = _proxy_ip_request("198.51.100.19", "203.0.113.234")
    assert rate_limit._resolve_client_ip(request) == "198.51.100.19"
