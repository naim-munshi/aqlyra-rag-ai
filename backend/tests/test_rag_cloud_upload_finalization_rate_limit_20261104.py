"""Regression for the production multi-file RAG Knowledge upload 429 incident.

The Redis upload-user bucket is intentionally limited to 20/hour, but a
single cloud upload performs two authenticated calls.  Independently enforce
the same quota on preparation and finalization so one ten-file batch does
not consume 20 intake slots.  This never disables owner isolation or allows
unbounded finalize requests.
"""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config.settings import settings
from app.core import rate_limit
from app.api.cloud_uploads import router as cloud_upload_router


class FakeRedis:
    def __init__(self):
        self.counts = {}

    def eval(self, script, number_of_keys, key, window_seconds):
        del script, number_of_keys
        count = self.counts.get(key, 0) + 1
        self.counts[key] = count
        return [count, int(window_seconds)]


def _synthetic_request(owner: str) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/documents/cloud/prepare",
        "headers": [],
        "client": ("127.0.0.1", 51000),
        "synthetic_owner": owner,
    })


def _enable_limiter(monkeypatch, limit: int = 10):
    redis = FakeRedis()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_UPLOAD_USER_LIMIT", limit)
    monkeypatch.setattr(settings, "RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS", 3600)
    monkeypatch.setattr(rate_limit, "get_rate_limit_redis", lambda: redis)
    # Only the test substitutes authentication. Production continues to
    # resolve a validated signed bearer token as the Redis owner identity.
    monkeypatch.setattr(
        rate_limit, "_authenticated_subject",
        lambda request: request.scope["synthetic_owner"],
    )
    return redis


def test_ten_cloud_uploads_consume_ten_prepare_slots_not_twenty(monkeypatch):
    redis = _enable_limiter(monkeypatch, limit=10)
    owner_request = _synthetic_request("synthetic-owner-a")

    # Exercise the same per-user rate dependencies used by both endpoints.
    for _ in range(10):
        rate_limit.limit_upload_request(owner_request)
        rate_limit.limit_cloud_finalize_request(owner_request)

    assert len(redis.counts) == 2
    assert sorted(redis.counts.values()) == [10, 10]

    with pytest.raises(HTTPException) as extra_prepare:
        rate_limit.limit_upload_request(owner_request)
    with pytest.raises(HTTPException) as extra_finalize:
        rate_limit.limit_cloud_finalize_request(owner_request)
    assert extra_prepare.value.status_code == 429
    assert extra_finalize.value.status_code == 429
    assert int(extra_prepare.value.headers["Retry-After"]) > 0
    assert int(extra_finalize.value.headers["Retry-After"]) > 0


def test_finalization_quota_remains_isolated_by_authenticated_user(monkeypatch):
    redis = _enable_limiter(monkeypatch, limit=1)
    owner_a = _synthetic_request("owner-a")
    owner_b = _synthetic_request("owner-b")
    rate_limit.limit_upload_request(owner_a)
    rate_limit.limit_cloud_finalize_request(owner_a)

    with pytest.raises(HTTPException) as blocked:
        rate_limit.limit_cloud_finalize_request(owner_a)
    assert blocked.value.status_code == 429

    rate_limit.limit_upload_request(owner_b)
    rate_limit.limit_cloud_finalize_request(owner_b)
    assert len(redis.counts) == 4


def test_cloud_endpoint_rate_dependencies_remain_enforced():
    routes = {
        route.endpoint.__name__: route
        for route in cloud_upload_router.routes
        if hasattr(route, "dependant")
    }
    prepare = routes["prepare_cloud_upload"]
    finalize = routes["finalize_cloud_upload_request"]
    proxy = routes["small_private_cloud_upload"]

    assert any(
        dependency.call is rate_limit.limit_upload_request
        for dependency in prepare.dependant.dependencies
    )
    assert any(
        dependency.call is rate_limit.limit_cloud_finalize_request
        for dependency in finalize.dependant.dependencies
    )
    assert any(
        dependency.call is rate_limit.limit_upload_request
        for dependency in proxy.dependant.dependencies
    )
    assert all(
        any(dependency.call is not None and dependency.call.__name__ == "get_current_user"
            for dependency in route.dependant.dependencies)
        for route in (prepare, finalize, proxy)
    )
