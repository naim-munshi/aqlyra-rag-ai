"""Mailbox ownership recovery from malicious pending registration."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.auth as auth_api
from app.config.settings import settings
from app.models.email_verification_code import EmailVerificationCode
from app.services.user_service import get_user_by_email


def _squatted_user(client: TestClient):
    return client.post("/api/v1/auth/register", json={
        "email": "real.owner@example.com",
        "username": "not_the_owner",
        "password": "AttackerPass123!",
    })


def _code_after_mailbox_request(client: TestClient, db_session: Session, sent_codes):
    # The owner may encounter a pending registration in its cooldown window.
    challenge = db_session.query(EmailVerificationCode).one()
    challenge.created_at = challenge.created_at.replace(
        year=challenge.created_at.year - 1
    )
    db_session.commit()
    response = client.post("/api/v1/auth/resend-verification", json={
        "email": "real.owner@example.com",
    })
    assert response.status_code == 200
    assert len(sent_codes) == 2
    return sent_codes[1], response.json()["verification_token"]


def test_mailbox_owner_can_claim_pending_registration_atomically(
    client: TestClient, db_session: Session, monkeypatch
):
    sent_codes = []
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(auth_api, "send_verification_email",
                        lambda *, recipient_email, code: sent_codes.append(code))
    squatted = _squatted_user(client)
    assert squatted.status_code == 201
    original_ticket = squatted.json()["verification_token"]

    code, ticket = _code_after_mailbox_request(client, db_session, sent_codes)
    bad_code = "000000" if code != "000000" else "999999"
    blocked = client.post("/api/v1/auth/claim-pending-email", json={
        "verification_token": ticket,
        "code": bad_code, "username": "real_owner",
        "new_password": "RealOwnerPass123!",
    })
    assert blocked.status_code == 400
    assert get_user_by_email(db_session, "real.owner@example.com").email_verified_at is None

    claimed = client.post("/api/v1/auth/claim-pending-email", json={
        "verification_token": ticket,
        "code": code, "username": "real_owner",
        "new_password": "RealOwnerPass123!",
    })
    assert claimed.status_code == 200
    assert claimed.json()["access_token"]

    profile = client.get("/api/v1/users/me", headers={
        "Authorization": "Bearer " + claimed.json()["access_token"]
    })
    assert profile.status_code == 200
    assert profile.json()["username"] == "real_owner"

    assert client.post("/api/v1/auth/login", json={
        "email": "real.owner@example.com", "password": "AttackerPass123!"
    }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "real.owner@example.com", "password": "RealOwnerPass123!"
    }).status_code == 200

    assert client.post("/api/v1/auth/claim-pending-email", json={
        "verification_token": ticket,
        "code": code, "username": "new_owner",
        "new_password": "AnotherPass123!",
    }).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={
        "verification_token": original_ticket, "code": sent_codes[0]
    }).status_code == 400


def test_claim_rejects_duplicate_username_without_consuming_code(
    client: TestClient, db_session: Session, monkeypatch
):
    sent_codes = []
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(auth_api, "send_verification_email",
                        lambda *, recipient_email, code: sent_codes.append(code))
    assert _squatted_user(client).status_code == 201
    assert client.post("/api/v1/auth/register", json={
        "email": "someone@example.com",
        "username": "occupied_name",
        "password": "OtherPass123!",
    }).status_code == 201
    code, ticket = _code_after_mailbox_request(client, db_session, sent_codes[:1])
    denied = client.post("/api/v1/auth/claim-pending-email", json={
        "verification_token": ticket, "code": code,
        "username": "occupied_name", "new_password": "RealOwnerPass123!",
    })
    assert denied.status_code == 400
    valid = client.post("/api/v1/auth/claim-pending-email", json={
        "verification_token": ticket, "code": code,
        "username": "unused_owner", "new_password": "RealOwnerPass123!",
    })
    assert valid.status_code == 200


def test_claim_malformed_input_cannot_mutate_account(
    client: TestClient, monkeypatch
):
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(auth_api, "send_verification_email", lambda **kwargs: None)
    assert _squatted_user(client).status_code == 201
    response = client.post("/api/v1/auth/claim-pending-email", json={
        "verification_token": "invalid", "code": "ABC123",
        "username": "??", "new_password": "short",
    })
    assert response.status_code == 422
