"""Direct Render JSON ingress is bounded before Pydantic/FastAPI buffering."""
from fastapi.testclient import TestClient

from app.middleware.json_body_limit import MAX_JSON_REQUEST_BYTES


def _oversized() -> bytes:
    return b'{"data":"' + b"x" * MAX_JSON_REQUEST_BYTES + b'"}'


def test_direct_unauthed_json_request_rejected_before_auth(client: TestClient):
    response = client.post(
        "/api/v1/conversations",
        content=_oversized(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "JSON request body is too large"}
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_forged_small_content_length_does_not_bypass_limit(client: TestClient):
    response = client.post(
        "/api/v1/conversations",
        content=_oversized(),
        headers={"Content-Type": "application/json", "Content-Length": "1"},
    )
    assert response.status_code == 413


def test_missing_content_type_still_limits_json(client: TestClient):
    response = client.post(
        "/api/v1/conversations",
        content=_oversized(),
        headers={"Content-Type": ""},
    )
    assert response.status_code == 413


def test_plus_json_mime_limited(client: TestClient):
    response = client.post(
        "/api/v1/conversations",
        content=_oversized(),
        headers={"Content-Type": "application/vnd.api+json"},
    )
    assert response.status_code == 413


def test_small_json_request_reaches_existing_auth_guard(client: TestClient):
    response = client.post(
        "/api/v1/conversations",
        json={"title": "Private test", "mode": "normal"},
    )
    assert response.status_code == 401


def test_multipart_streaming_requests_keep_existing_upload_handling(client: TestClient):
    # A declared file length greater than the JSON cap must not trigger
    # the JSON 413 guard; upload streaming has separate per-file limits.
    response = client.post(
        "/api/v1/documents/upload",
        data={"comment": "test"},
        files={"file": ("probe.txt", b"abc", "text/plain")},
        headers={"Content-Length": str(MAX_JSON_REQUEST_BYTES + 5)},
    )
    assert response.status_code != 413


def test_auth_still_uses_stricter_limit(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        content=b'{"payload":"' + b"x" * 20_000 + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Authentication request is too large"
