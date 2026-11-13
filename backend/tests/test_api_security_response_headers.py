"""Security headers are applied by API middleware on every response.

All tests use disposable test services, never the production database.
"""
from fastapi.testclient import TestClient


def test_private_api_auth_failure_is_not_cacheable(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.headers.get("cache-control") == "private, no-store"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-request-id")


def test_api_liveness_is_not_cacheable_or_sniffable(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "private, no-store"
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_existing_cache_policy_is_not_overwritten_by_middleware():
    from pathlib import Path
    from app.middleware import observability

    source = Path(observability.__file__).read_text(encoding="utf-8")
    assert 'if "Cache-Control" not in response.headers:' in source
    assert 'response.headers["Cache-Control"] = "private, no-store"' in source


def test_production_api_hsts_without_subdomain_preload(
    client: TestClient, monkeypatch,
) -> None:
    from app.config.settings import settings

    monkeypatch.setattr(settings, "APP_ENV", "production")
    for path in ("/api/v1/health", "/api/v1/users/me"):
        response = client.get(path)
        assert response.status_code in (200, 401)
        assert response.headers.get("strict-transport-security") == "max-age=31536000"
        assert "includeSubDomains" not in response.headers["strict-transport-security"]
        assert "preload" not in response.headers["strict-transport-security"]


def test_nonproduction_api_does_not_assert_hsts(
    client: TestClient, monkeypatch,
) -> None:
    from app.config.settings import settings

    monkeypatch.setattr(settings, "APP_ENV", "development")
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("strict-transport-security") is None
