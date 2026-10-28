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
    assert body["cloud_storage"]["scope"] == "database_aggregate"
    for metric in ("claimed", "stale_claimed", "cleanup_candidates", "failed_intents"):
        assert body["cloud_storage"][metric] == 0
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



def test_prometheus_metrics_are_private_to_verified_admin(
    client: TestClient, db_session, monkeypatch,
) -> None:
    """Hidden OpenAPI route is not security; enforce the actual admin gate."""
    reset_metrics_for_tests()
    admin_id, admin_token = _new_user(client, "metricsowner")
    ordinary_id, ordinary_token = _new_user(client, "metricsother")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    anonymous = client.get("/api/v1/metrics")
    assert anonymous.status_code == 401
    assert "aqlyra_http_requests_total" not in anonymous.text

    unauthorized = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer " + ordinary_token},
    )
    assert unauthorized.status_code == 403
    assert "aqlyra_http_requests_total" not in unauthorized.text

    allowed = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert allowed.status_code == 200
    assert "aqlyra_http_requests_total" in allowed.text
    assert allowed.headers["cache-control"] == "private, no-store"
    assert "text/plain" in allowed.headers["content-type"]

    user = db_session.get(User, admin_id)
    assert user is not None
    user.email_verified_at = None
    db_session.flush()
    revoked = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert revoked.status_code == 403
    assert "aqlyra_http_requests_total" not in revoked.text
    assert ordinary_id not in revoked.text



def test_guest_ip_audit_visible_only_to_verified_allowlisted_admin(
    client: TestClient, db_session, monkeypatch,
) -> None:
    """IP traffic is personally identifying and never a public statistic."""
    admin_id, admin_token = _new_user(client, "guestipadmin")
    other_id, other_token = _new_user(client, "guestipother")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    # No live Redis is needed: prove the full HTTP authorization boundary.
    monkeypatch.setattr(
        "app.api.admin.recent_guest_traffic",
        lambda: [{
            "ip": "203.0.113.41",
            "requests": 3,
            "last_seen_utc": 1780000000,
        }],
    )

    anonymous = client.get("/api/v1/admin/guest-traffic")
    assert anonymous.status_code == 401
    assert "203.0.113.41" not in anonymous.text

    unauthorized = client.get(
        "/api/v1/admin/guest-traffic",
        headers={"Authorization": "Bearer " + other_token},
    )
    assert unauthorized.status_code == 403
    assert "203.0.113.41" not in unauthorized.text

    allowed = client.get(
        "/api/v1/admin/guest-traffic",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "private, no-store"
    assert allowed.json()["entries"] == [{
        "ip": "203.0.113.41",
        "requests": 3,
        "last_seen_utc": 1780000000,
    }]
    assert allowed.json()["retention_hours"] == 24

    admin = db_session.get(User, admin_id)
    assert admin is not None
    admin.email_verified_at = None
    db_session.flush()
    revoked = client.get(
        "/api/v1/admin/guest-traffic",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert revoked.status_code == 403
    assert "203.0.113.41" not in revoked.text
    assert other_id not in revoked.text
