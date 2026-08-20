from fastapi.testclient import TestClient

from app.config.settings import settings


USER = {
    "username": "voiceuser",
    "email": "voiceuser@example.com",
    "password": "TestPass123!",
}


def authenticate(
    client: TestClient,
) -> dict[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json=USER,
    )

    assert register.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": USER["email"],
            "password": USER["password"],
        },
    )

    assert login.status_code == 200

    return {
        "Authorization": (
            "Bearer "
            + login.json()["access_token"]
        )
    }


def configure_livekit(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "LIVEKIT_URL",
        "wss://test.livekit.cloud",
    )
    monkeypatch.setattr(
        settings,
        "LIVEKIT_API_KEY",
        "test-api-key",
    )
    monkeypatch.setattr(
        settings,
        "LIVEKIT_API_SECRET",
        "test-api-secret-at-least-32-bytes-long",
    )
    monkeypatch.setattr(
        settings,
        "VOICE_AGENT_NAME",
        "aqlyra-voice",
    )


def test_voice_session_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/voice/session",
        json={
            "mode": "normal",
        },
    )

    assert response.status_code == 401


def test_authenticated_user_can_create_voice_session(
    client: TestClient,
    monkeypatch,
) -> None:
    configure_livekit(
        monkeypatch
    )

    headers = authenticate(client)

    response = client.post(
        "/api/v1/voice/session",
        headers=headers,
        json={
            "mode": "normal",
            "title": "Voice test",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["server_url"] == (
        "wss://test.livekit.cloud"
    )
    assert payload["participant_token"]
    assert payload["room_name"].startswith(
        "aqlyra-"
    )
    assert payload["conversation_id"]
    assert payload["mode"] == "normal"


def test_voice_session_fails_cleanly_without_config(
    client: TestClient,
    monkeypatch,
) -> None:
    headers = authenticate(client)

    monkeypatch.setattr(
        settings,
        "LIVEKIT_URL",
        "",
    )
    monkeypatch.setattr(
        settings,
        "LIVEKIT_API_KEY",
        "",
    )
    monkeypatch.setattr(
        settings,
        "LIVEKIT_API_SECRET",
        "",
    )

    response = client.post(
        "/api/v1/voice/session",
        headers=headers,
        json={
            "mode": "normal",
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "Voice service is not configured"
    )
