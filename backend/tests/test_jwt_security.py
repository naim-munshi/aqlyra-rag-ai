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


@pytest.mark.parametrize("kind", ["access", "refresh", "email_verification"])
@pytest.mark.parametrize("claim", ["exp", "iat", "sub", "type"])
def test_required_claims_cannot_be_omitted(kind, claim):
    from app.auth.security import create_refresh_token, decode_refresh_token_with_version
    creators = {
        "access": lambda: create_access_token("jwt-user"),
        "refresh": lambda: create_refresh_token("jwt-user"),
        "email_verification": lambda: create_email_verification_token(
            subject="jwt-user", challenge_id="challenge-123"),
    }
    decoders = {
        "access": decode_access_token,
        "refresh": decode_refresh_token_with_version,
        "email_verification": decode_email_verification_token,
    }
    claims = jwt.decode(creators[kind](), settings.SECRET_KEY, algorithms=["HS256"])
    del claims[claim]
    malformed = jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256")
    error = InvalidVerificationTokenError if kind == "email_verification" else InvalidTokenError
    with pytest.raises(error):
        decoders[kind](malformed)


@pytest.mark.parametrize("subject", ["", "   "])
@pytest.mark.parametrize("kind", ["access", "refresh", "email_verification"])
def test_blank_identity_is_rejected(kind, subject):
    from app.auth.security import create_refresh_token, decode_refresh_token_with_version
    if kind == "access":
        token, decoder, error = create_access_token(subject), decode_access_token, InvalidTokenError
    elif kind == "refresh":
        token, decoder, error = create_refresh_token(subject), decode_refresh_token_with_version, InvalidTokenError
    else:
        token = create_email_verification_token(subject=subject, challenge_id="challenge")
        decoder, error = decode_email_verification_token, InvalidVerificationTokenError
    with pytest.raises(error):
        decoder(token)


def test_refresh_roundtrip_and_cross_type_rejection():
    from app.auth.security import create_refresh_token, decode_refresh_token_with_version
    token = create_refresh_token("jwt-user", token_version=4)
    assert decode_refresh_token_with_version(token) == ("jwt-user", 4)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
    with pytest.raises(InvalidVerificationTokenError):
        decode_email_verification_token(token)
    with pytest.raises(InvalidTokenError):
        decode_refresh_token_with_version(create_access_token("jwt-user"))


def test_legacy_access_version_zero_remains_supported():
    claims = jwt.decode(create_access_token("legacy-user"), settings.SECRET_KEY, algorithms=["HS256"])
    del claims["ver"]
    assert decode_access_token(jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256")) == "legacy-user"


@pytest.mark.parametrize("challenge_id", ["", "   "])
def test_blank_email_challenge_rejected(challenge_id):
    token = create_email_verification_token(subject="jwt-user", challenge_id=challenge_id)
    with pytest.raises(InvalidVerificationTokenError):
        decode_email_verification_token(token)
