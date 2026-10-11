"""JWT contract and algorithm-confusion regression tests."""

from datetime import timedelta

import jwt
import pytest

from app.auth.security import (
    InvalidTokenError,
    InvalidVerificationTokenError,
    create_access_token,
    create_email_verification_token,
    decode_access_token,
    decode_email_verification_token,
)
from app.config.settings import settings


def test_access_token_is_hs256_and_interoperable() -> None:
    token = create_access_token("jwt-user")

    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"

    claims = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],
    )

    assert claims["sub"] == "jwt-user"
    assert claims["type"] == "access"
    assert decode_access_token(token) == "jwt-user"


def test_unsigned_jwt_is_rejected() -> None:
    token = jwt.encode(
        {"sub": "attacker", "type": "access"},
        key="",
        algorithm="none",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_invalid_signature_is_rejected() -> None:
    token = jwt.encode(
        {"sub": "attacker", "type": "access"},
        key="attacker-secret",
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_expired_jwt_is_rejected() -> None:
    token = create_access_token(
        "expired-user",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_email_verification_token_cannot_authenticate() -> None:
    token = create_email_verification_token(
        subject="jwt-user",
        challenge_id="challenge-123",
    )

    assert decode_email_verification_token(token) == (
        "jwt-user",
        "challenge-123",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_access_token_cannot_verify_email() -> None:
    token = create_access_token("jwt-user")

    with pytest.raises(InvalidVerificationTokenError):
        decode_email_verification_token(token)
