"""Refresh-token family rotation, concurrency grace, and replay revocation."""
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import decode_refresh_token_claims
from app.core.datetime_utils import utc_now_naive
from app.models.refresh_session import RefreshSession
from app.services.refresh_session_service import REFRESH_REUSE_GRACE_SECONDS


def _login(client: TestClient, username: str) -> dict:
    email = f"{username}@example.com"
    registered = client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "password": "SecurePass123!",
    })
    assert registered.status_code == 201
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "SecurePass123!",
    })
    assert response.status_code == 200
    return response.json()


def _refresh(client: TestClient, token: str):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": token})


def test_refresh_rotation_preserves_expiry_and_grace_retries_are_idempotent(client):
    initial = _login(client, "refreshowner")
    original_refresh = initial["refresh_token"]
    original_access = initial["access_token"]
    _, _, session_id, generation, _ = decode_refresh_token_claims(original_refresh)
    assert generation == 0

    rotated = _refresh(client, original_refresh)
    assert rotated.status_code == 200
    first_data = rotated.json()
    successor = first_data["refresh_token"]
    assert successor != original_refresh
    _, _, next_session_id, next_generation, _ = decode_refresh_token_claims(successor)
    assert next_session_id == session_id
    assert next_generation == 1

    # Two parallel BFF requests can present the old cookie during the grace window.
    retry = _refresh(client, original_refresh)
    assert retry.status_code == 200
    assert retry.json()["refresh_token"] == successor

    # The original bearer ticket is still a valid access JWT until its own expiry.
    assert client.get("/api/v1/users/me", headers={
        "Authorization": f"Bearer {original_access}",
    }).status_code == 200


def test_refresh_replay_after_grace_revokes_all_user_sessions(client, db_session):
    initial = _login(client, "refreshreplay")
    original_refresh = initial["refresh_token"]
    original_access = initial["access_token"]
    rotated = _refresh(client, original_refresh)
    assert rotated.status_code == 200
    successor = rotated.json()["refresh_token"]
    _, _, session_id, generation, token_id = decode_refresh_token_claims(original_refresh)

    original = db_session.get(RefreshSession, (session_id, generation))
    assert original is not None
    original.consumed_at = utc_now_naive() - timedelta(
        seconds=REFRESH_REUSE_GRACE_SECONDS + 2,
    )
    db_session.commit()

    replay = _refresh(client, original_refresh)
    assert replay.status_code == 401
    assert "refresh token" not in replay.text.lower()

    # Replay detection bumps auth_epoch, invalidating both current access and refresh tickets.
    assert client.get("/api/v1/users/me", headers={
        "Authorization": f"Bearer {original_access}",
    }).status_code == 401
    assert _refresh(client, successor).status_code == 401

    family = db_session.scalars(
        select(RefreshSession).where(RefreshSession.session_id == session_id)
    ).all()
    assert family
    assert all(row.revoked_at is not None for row in family)


def test_refresh_token_cannot_be_used_as_access_token(client):
    initial = _login(client, "refreshtypecheck")
    response = client.get("/api/v1/users/me", headers={
        "Authorization": f"Bearer {initial["refresh_token"]}",
    })
    assert response.status_code == 401


def test_logout_invalidates_refresh_token(client):
    initial = _login(client, "refreshlogout")
    response = client.post("/api/v1/auth/logout", headers={
        "Authorization": f"Bearer {initial["access_token"]}",
    })
    assert response.status_code == 200
    assert _refresh(client, initial["refresh_token"]).status_code == 401
