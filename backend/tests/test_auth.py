from fastapi.testclient import TestClient


USER_DATA = {
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "TestPass123!",
}


def register_user(
    client: TestClient,
):
    return client.post(
        "/api/v1/auth/register",
        json=USER_DATA,
    )


def login_user(
    client: TestClient,
):
    return client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_DATA["email"],
            "password": USER_DATA["password"],
        },
    )


def test_register_user(
    client: TestClient,
) -> None:
    response = register_user(client)

    assert response.status_code == 201

    payload = response.json()

    assert payload["username"] == "testuser"
    assert payload["email"] == "testuser@example.com"
    assert payload["is_active"] is True
    assert "password" not in payload
    assert "hashed_password" not in payload


def test_login_returns_access_token(
    client: TestClient,
) -> None:
    register_response = register_user(client)

    assert register_response.status_code == 201

    login_response = login_user(client)

    assert login_response.status_code == 200

    payload = login_response.json()

    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["access_token"]


def test_profile_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/users/me"
    )

    assert response.status_code == 401


def test_authenticated_user_can_read_profile(
    client: TestClient,
) -> None:
    register_response = register_user(client)

    assert register_response.status_code == 201

    login_response = login_user(client)

    assert login_response.status_code == 200

    token = login_response.json()[
        "access_token"
    ]

    response = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["username"] == "testuser"
    assert payload["email"] == "testuser@example.com"
    assert payload["is_active"] is True
