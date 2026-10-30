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
