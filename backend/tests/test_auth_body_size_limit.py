"""The public Render ingress must reject oversized auth JSON before parsing."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("route", [
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/google",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/request-password-reset",
    "/api/v1/auth/reset-password",
])
def test_oversized_direct_auth_request_rejected_without_backend_processing(
    client: TestClient, route: str,
):
    response = client.post(
        route,
        content=b'{"payload":"' + b"x" * 17_000 + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Authentication request is too large"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "xxxxx" not in response.text


def test_bogus_short_content_length_cannot_bypass_actual_body_limit(
    client: TestClient,
):
    response = client.post(
        "/api/v1/auth/login",
        content=b'{"payload":"' + b"x" * 17_000 + b'"}',
        headers={
            "Content-Type": "application/json",
            "Content-Length": "1",
        },
    )
    assert response.status_code == 413


def test_legitimate_below_limit_auth_request_reaches_normal_validation(
    client: TestClient,
):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "not-registered@example.com",
            "password": "ValidLengthPassword123!",
        },
    )
    assert response.status_code == 401
