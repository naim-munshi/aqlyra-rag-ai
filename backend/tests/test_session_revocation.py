"""Server-side access token revocation across independent requests."""
from fastapi.testclient import TestClient


def _register_login(client: TestClient, username: str) -> str:
    email = f"{username}@example.com"
    created = client.post("/api/v1/auth/register", json={
        "username": username, "email": email,
        "password": "SecurePass123!",
    })
    assert created.status_code == 201
    signed_in = client.post("/api/v1/auth/login", json={
        "email": email, "password": "SecurePass123!",
    })
    assert signed_in.status_code == 200
    return signed_in.json()["access_token"]


def test_logout_revokes_all_existing_tokens_but_allows_new_login(client: TestClient):
    token = _register_login(client, "signoutowner")
    other = _register_login(client, "signoutother")
    owner_header = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/users/me", headers=owner_header).status_code == 200
    revoke = client.post("/api/v1/auth/logout", headers=owner_header)
    assert revoke.status_code == 200
    assert revoke.json() == {"success": True}
    assert client.get("/api/v1/users/me", headers=owner_header).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=owner_header).status_code == 401
    assert client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {other}"}
    ).status_code == 200

    fresh = client.post("/api/v1/auth/login", json={
        "email": "signoutowner@example.com", "password": "SecurePass123!",
    })
    assert fresh.status_code == 200
    new_token = fresh.json()["access_token"]
    assert client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {new_token}"},
    ).status_code == 200


def test_logout_requires_authenticated_user(client: TestClient):
    assert client.post("/api/v1/auth/logout").status_code == 401
    assert client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    ).status_code == 401
