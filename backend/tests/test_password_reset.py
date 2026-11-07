"""Password recovery should never expose accounts or create replayable codes."""
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.auth as auth_api
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.password_reset_code import PasswordResetCode
from app.models.user import User
from app.services.email_service import EmailDeliveryError

EMAIL = "recovery@example.com"
PASSWORD = "OriginalPass123!"
NEW_PASSWORD = "NewSecurePass456!"

def register(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "username": "recovery", "password": PASSWORD},
    )
    assert response.status_code == 201

def request_code(client: TestClient, email: str = EMAIL):
    return client.post("/api/v1/auth/request-password-reset", json={"email": email})

def confirm(client: TestClient, code: str, password: str = NEW_PASSWORD, email: str = EMAIL):
    return client.post(
        "/api/v1/auth/reset-password",
        json={"email": email, "code": code, "new_password": password},
    )

def sign_in(client: TestClient, password: str):
    return client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": password},
    )

def test_unknown_account_is_not_disclosed(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_api, "send_password_reset_email",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected email")),
    )
    response = request_code(client, "nonexistent@example.com")
    assert response.status_code == 200
    assert "eligible" in response.json()["message"]
    assert "token" not in response.json()
    assert confirm(client, "123456", email="nonexistent@example.com").status_code == 400

def test_reset_revokes_existing_jwt_and_blocks_code_replay(
    client: TestClient, monkeypatch,
) -> None:
    register(client)
    old_login = sign_in(client, PASSWORD)
    assert old_login.status_code == 200
    old_token = old_login.json()["access_token"]
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api, "send_password_reset_email",
        lambda *, recipient_email, code: sent.append(code),
    )
    sent_response = request_code(client)
    assert sent_response.status_code == 200
    assert "code" not in sent_response.json()
    assert len(sent) == 1
    incorrect = "000000" if sent[0] != "000000" else "999999"
    assert confirm(client, incorrect).status_code == 400
    success = confirm(client, sent[0])
    assert success.status_code == 200
    assert sign_in(client, PASSWORD).status_code == 401
    assert sign_in(client, NEW_PASSWORD).status_code == 200
    assert client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {old_token}"}
    ).status_code == 401
    assert confirm(client, sent[0]).status_code == 400

def test_rate_limit_cooldown_expiry_and_last_code_wins(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    register(client)
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api, "send_password_reset_email",
        lambda *, recipient_email, code: sent.append(code),
    )
    assert request_code(client).status_code == 200
    assert request_code(client).status_code == 200
    assert len(sent) == 1
    user = db_session.query(User).filter_by(email=EMAIL).one()
    challenge = db_session.get(PasswordResetCode, user.id)
    assert challenge is not None
    challenge.created_at = utc_now_naive() - timedelta(minutes=2)
    db_session.commit()
    assert request_code(client).status_code == 200
    assert len(sent) == 2
    assert confirm(client, sent[0]).status_code == 400
    challenge = db_session.get(PasswordResetCode, user.id)
    assert challenge is not None
    challenge.expires_at = utc_now_naive() - timedelta(seconds=1)
    db_session.commit()
    assert confirm(client, sent[1]).status_code == 400
    assert sign_in(client, PASSWORD).status_code == 200

def test_wrong_attempt_limit(client: TestClient, monkeypatch) -> None:
    register(client)
    monkeypatch.setattr(settings, "PASSWORD_RESET_MAX_ATTEMPTS", 3)
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api, "send_password_reset_email",
        lambda *, recipient_email, code: sent.append(code),
    )
    assert request_code(client).status_code == 200
    incorrect = "000000" if sent[0] != "000000" else "999999"
    for _ in range(3):
        assert confirm(client, incorrect).status_code == 400
    assert confirm(client, sent[0]).status_code == 400
    assert sign_in(client, PASSWORD).status_code == 200

def test_smtp_failure_does_not_disclose_account(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    register(client)
    def fail(**kwargs) -> None:
        raise EmailDeliveryError("simulated SMTP failure")
    monkeypatch.setattr(auth_api, "send_password_reset_email", fail)
    response = request_code(client)
    assert response.status_code == 200
    user = db_session.query(User).filter_by(email=EMAIL).one()
    assert db_session.get(PasswordResetCode, user.id) is None

def test_unverified_account_does_not_get_reset_code(
    client: TestClient, monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(auth_api, "send_verification_email", lambda **kwargs: None)
    register(client)
    def fail(**kwargs) -> None:
        raise AssertionError("must not mail unverified accounts")
    monkeypatch.setattr(auth_api, "send_password_reset_email", fail)
    assert request_code(client).status_code == 200
    assert confirm(client, "123456").status_code == 400

def test_invalid_input_is_rejected(client: TestClient) -> None:
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"email": EMAIL, "code": "abc", "new_password": "short"},
    ).status_code == 422
