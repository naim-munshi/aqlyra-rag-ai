"""Owner-only operational metrics: tenant isolation and safe aggregate responses."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings, settings
from app.core.monitoring import admin_http_snapshot, reset_metrics_for_tests
from app.models.user import User


def _new_user(client: TestClient, label: str) -> tuple[str, str]:
    data = {
        "username": "admin_" + label + uuid4().hex[:8],
        "email": label + uuid4().hex[:8] + "@example.com",
        "password": "TestPassword012!",
    }
    assert client.post("/api/v1/auth/register", json=data).status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": data["email"], "password": data["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer " + token}
    ).json()
    return me["id"], token


def test_admin_is_disabled_by_default(client: TestClient, monkeypatch) -> None:
    uid, token = _new_user(client, "disabled")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    assert client.get("/api/v1/admin/overview").status_code == 401
    result = client.get(
        "/api/v1/admin/overview", headers={"Authorization": "Bearer " + token}
    )
    assert result.status_code == 403
    assert uid not in result.text


def test_owner_can_read_only_aggregates(
    client: TestClient, monkeypatch,
) -> None:
    admin_id, admin_token = _new_user(client, "owner")
    user_id, user_token = _new_user(client, "other")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    forbidden = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + user_token},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store, private"
    body = allowed.json()
    assert body["users"]["registered_total"] == 2
    assert body["users"]["active_accounts"] == 2
    assert len(body["users"]["signups_last_7_days"]) == 7
    assert sum(day["count"] for day in body["users"]["signups_last_7_days"]) == 2
    assert body["traffic"]["scope"] == "single_backend_process"
    assert "request_total" in body["traffic"]
    serialized = allowed.text
    for private in (admin_id, user_id, admin_token, user_token, "@example.com"):
        assert private not in serialized
    assert "username" not in serialized
    assert "ip_address" not in serialized
    assert "access_token" not in serialized


def test_unverified_allowlisted_user_cannot_read(
    client: TestClient, db_session, monkeypatch,
) -> None:
    user_id, token = _new_user(client, "pending")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    user = db_session.get(User, user_id)
    assert user is not None
    user.email_verified_at = None
    db_session.flush()
    assert client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + token},
    ).status_code == 403


def test_monitoring_does_not_include_raw_user_paths() -> None:
    reset_metrics_for_tests()
    snap = admin_http_snapshot()
    assert snap["request_total"] == 0
    assert snap["routes"] == []


@pytest.mark.parametrize("value", [
    "user@example.com", "admin", "123", "f" * 120,
    "9d4c4bc2-a367-485d-b332-60a73d894e9b,admin",
])
def test_invalid_admin_ids_rejected(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, ADMIN_USER_IDS=value)
