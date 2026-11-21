"""Persistent sign-in regression: no database migrations or real sessions.

Refresh is a distinct signed JWT, never accepted as an API bearer. Sessions
expire after a fixed absolute deadline and logout/password reset revokes all
old tokens through auth_epoch.
"""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token_with_version,
)


def register_and_sign_in(client: TestClient, identity: str):
    email = f"{identity}@example.com"
    created = client.post("/api/v1/auth/register", json={
        "email": email,
        "username": identity,
        "password": "SyntheticPersist123!",
    })
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "SyntheticPersist123!",
    })
    assert login.status_code == 200, login.text
    return login.json()


def test_fast_login_returns_public_user_profile_without_extra_me_request(client: TestClient):
    login = register_and_sign_in(client, "persistentfast")
    assert login["refresh_token"]
    assert login["user"]["email"] == "persistentfast@example.com"
    assert login["user"]["username"] == "persistentfast"
    assert "password" not in str(login["user"]).lower()
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json() == login["user"]


def test_refresh_replaces_expiring_access_token_but_never_extends_refresh_deadline(
    client: TestClient,
):
    login = register_and_sign_in(client, "persistentrestore")
    refresh = login["refresh_token"]
    renewed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert renewed.status_code == 200, renewed.text
    payload = renewed.json()
    assert payload["user"]["id"] == login["user"]["id"]
    assert payload["access_token"]
    assert payload["refresh_token"] is None
    assert client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer " + payload["access_token"]},
    ).status_code == 200
    assert decode_refresh_token_with_version(refresh)[0] == login["user"]["id"]


def test_refresh_jwt_is_never_accepted_as_access_and_vice_versa(client: TestClient):
    login = register_and_sign_in(client, "persisttypes")
    refresh = login["refresh_token"]
    access = login["access_token"]
    assert client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refresh}"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": access},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "x" * 64},
    ).status_code == 401


def test_expired_ticket_fails_even_with_valid_user(client: TestClient):
    login = register_and_sign_in(client, "persistexpire")
    token = create_refresh_token(
        login["user"]["id"],
        token_version=0,
        expires_delta=timedelta(seconds=-1),
    )
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": token},
    ).status_code == 401


def test_expired_access_can_be_restored_using_valid_refresh(client: TestClient):
    login = register_and_sign_in(client, "persistaccess")
    expired_access = create_access_token(
        login["user"]["id"],
        token_version=0,
        expires_delta=timedelta(seconds=-1),
    )
    assert client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_access}"},
    ).status_code == 401
    renewed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]},
    )
    assert renewed.status_code == 200
    assert client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {renewed.json()['access_token']}"},
    ).status_code == 200


def test_logout_revokes_refresh_ticket_across_clients_and_other_user_survives(
    client: TestClient,
):
    owner = register_and_sign_in(client, "persistowner")
    other = register_and_sign_in(client, "persistother")
    assert client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    ).status_code == 200

    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": owner["refresh_token"]},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": other["refresh_token"]},
    ).status_code == 200
