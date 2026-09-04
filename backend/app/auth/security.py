from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings


password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


class InvalidTokenError(Exception):
    """Raised when an access token is invalid or expired."""


class InvalidVerificationTokenError(Exception):
    """Raised when an email verification ticket is invalid."""


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)

    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidTokenError(
            "Invalid or expired access token",
        ) from exc

    subject = payload.get("sub")
    token_type = payload.get("type")

    if not isinstance(subject, str):
        raise InvalidTokenError(
            "Token subject is missing",
        )

    if token_type != "access":
        raise InvalidTokenError(
            "Invalid token type",
        )

    return subject


def create_email_verification_token(
    *,
    subject: str,
    challenge_id: str,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=(
            settings
            .EMAIL_VERIFICATION_CODE_TTL_MINUTES
        ),
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "cid": challenge_id,
        "type": "email_verification",
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_email_verification_token(
    token: str,
) -> tuple[str, str]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidVerificationTokenError(
            "Invalid or expired verification request",
        ) from exc

    subject = payload.get("sub")
    challenge_id = payload.get("cid")
    token_type = payload.get("type")

    if (
        not isinstance(subject, str)
        or not isinstance(challenge_id, str)
        or token_type != "email_verification"
    ):
        raise InvalidVerificationTokenError(
            "Invalid or expired verification request",
        )

    return subject, challenge_id
