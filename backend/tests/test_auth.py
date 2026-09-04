from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.auth as auth_api
from app.config.settings import settings
from app.models.email_verification_code import (
    EmailVerificationCode,
)
from app.services.email_service import EmailDeliveryError
from app.services.google_identity_service import GoogleIdentity
from app.services.user_service import get_user_by_email


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


def test_email_account_requires_valid_otp_before_login(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    sent_codes: list[str] = []

    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_REQUIRED",
        True,
    )
    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        lambda *, recipient_email, code: sent_codes.append(
            code
        ),
    )

    registered = register_user(client)

    assert registered.status_code == 201
    assert registered.json()["verification_required"] is True
    assert registered.json()["verification_email_sent"] is True
    assert len(sent_codes) == 1
    verification_token = registered.json()[
        "verification_token"
    ]

    blocked_login = login_user(client)

    assert blocked_login.status_code == 403
    assert blocked_login.json()["detail"] == (
        "Email verification required"
    )

    wrong_code = (
        "999999"
        if sent_codes[0] == "000000"
        else "000000"
    )
    rejected = client.post(
        "/api/v1/auth/verify-email",
        json={
            "code": wrong_code,
            "verification_token": verification_token,
        },
    )

    assert rejected.status_code == 400

    verified = client.post(
        "/api/v1/auth/verify-email",
        json={
            "code": sent_codes[0],
            "verification_token": verification_token,
        },
    )

    assert verified.status_code == 200
    assert verified.json()["access_token"]

    user = get_user_by_email(
        db_session,
        USER_DATA["email"],
    )

    assert user is not None
    assert user.email_verified_at is not None
    assert login_user(client).status_code == 200

    reused = client.post(
        "/api/v1/auth/verify-email",
        json={
            "code": sent_codes[0],
            "verification_token": verification_token,
        },
    )

    assert reused.status_code == 400


def test_email_otp_locks_after_maximum_wrong_attempts(
    client: TestClient,
    monkeypatch,
) -> None:
    sent_codes: list[str] = []

    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_REQUIRED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_MAX_ATTEMPTS",
        3,
    )
    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        lambda *, recipient_email, code: sent_codes.append(
            code
        ),
    )

    registered = register_user(client)

    assert registered.status_code == 201
    verification_token = registered.json()[
        "verification_token"
    ]

    wrong_code = (
        "999999"
        if sent_codes[0] == "000000"
        else "000000"
    )

    for _ in range(3):
        rejected = client.post(
            "/api/v1/auth/verify-email",
            json={
                "code": wrong_code,
                "verification_token": verification_token,
            },
        )
        assert rejected.status_code == 400

    locked = client.post(
        "/api/v1/auth/verify-email",
        json={
            "code": sent_codes[0],
            "verification_token": verification_token,
        },
    )

    assert locked.status_code == 400


def test_resend_verification_enforces_cooldown(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    sent_codes: list[str] = []

    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_REQUIRED",
        True,
    )
    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        lambda *, recipient_email, code: sent_codes.append(
            code
        ),
    )

    assert register_user(client).status_code == 201

    too_soon = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": USER_DATA["email"]},
    )

    assert too_soon.status_code == 429
    assert int(too_soon.headers["retry-after"]) >= 1

    latest = db_session.query(
        EmailVerificationCode
    ).one()
    latest.created_at = latest.created_at.replace(
        year=latest.created_at.year - 1
    )
    db_session.commit()

    resent = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": USER_DATA["email"]},
    )

    assert resent.status_code == 200
    assert len(sent_codes) == 2


def test_registration_stays_unverified_when_email_delivery_fails(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_REQUIRED",
        True,
    )

    def fail_delivery(**kwargs) -> None:
        del kwargs
        raise EmailDeliveryError("simulated failure")

    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        fail_delivery,
    )

    registered = register_user(client)

    assert registered.status_code == 201
    assert registered.json()["verification_email_sent"] is False
    assert login_user(client).status_code == 403


def test_new_registration_replaces_unverified_squatted_account(
    client: TestClient,
    monkeypatch,
) -> None:
    sent_codes: list[str] = []

    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_REQUIRED",
        True,
    )
    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        lambda *, recipient_email, code: sent_codes.append(
            code
        ),
    )

    attacker = client.post(
        "/api/v1/auth/register",
        json={
            "username": "attacker_name",
            "email": "victim@gmail.com",
            "password": "AttackerPass123!",
        },
    )
    owner = client.post(
        "/api/v1/auth/register",
        json={
            "username": "real_owner",
            "email": "victim@gmail.com",
            "password": "OwnerPass123!",
        },
    )

    assert attacker.status_code == 201
    assert owner.status_code == 201

    stale = client.post(
        "/api/v1/auth/verify-email",
        json={
            "code": sent_codes[0],
            "verification_token": attacker.json()[
                "verification_token"
            ],
        },
    )

    assert stale.status_code == 400

    verified = client.post(
        "/api/v1/auth/verify-email",
        json={
            "code": sent_codes[1],
            "verification_token": owner.json()[
                "verification_token"
            ],
        },
    )

    assert verified.status_code == 200

    attacker_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "victim@gmail.com",
            "password": "AttackerPass123!",
        },
    )
    owner_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "victim@gmail.com",
            "password": "OwnerPass123!",
        },
    )

    assert attacker_login.status_code == 401
    assert owner_login.status_code == 200


def test_verified_google_credential_creates_stable_account(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth_api,
        "verify_google_credential",
        lambda credential: GoogleIdentity(
            subject="google-subject-123",
            email="google.user@gmail.com",
        ),
    )

    first = client.post(
        "/api/v1/auth/google",
        json={"credential": "x" * 20},
    )
    second = client.post(
        "/api/v1/auth/google",
        json={"credential": "y" * 20},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    user = get_user_by_email(
        db_session,
        "google.user@gmail.com",
    )

    assert user is not None
    assert user.email_verified_at is not None
    assert user.google_subject == "google-subject-123"
    assert (
        db_session.query(type(user)).count()
        == 1
    )


def test_google_sign_in_reclaims_unverified_squatted_email(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "EMAIL_VERIFICATION_REQUIRED",
        True,
    )
    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        lambda **kwargs: None,
    )

    squatted = client.post(
        "/api/v1/auth/register",
        json={
            "username": "squatter",
            "email": "google.owner@gmail.com",
            "password": "AttackerPass123!",
        },
    )

    assert squatted.status_code == 201

    monkeypatch.setattr(
        auth_api,
        "verify_google_credential",
        lambda credential: GoogleIdentity(
            subject="real-google-subject",
            email="google.owner@gmail.com",
        ),
    )

    reclaimed = client.post(
        "/api/v1/auth/google",
        json={"credential": "g" * 20},
    )
    attacker_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "google.owner@gmail.com",
            "password": "AttackerPass123!",
        },
    )

    assert reclaimed.status_code == 200
    assert attacker_login.status_code == 401
