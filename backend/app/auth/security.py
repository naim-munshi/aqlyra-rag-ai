import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError as JWTError
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
    token_version: int = 0,
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
        "ver": token_version,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def refresh_token_jti(session_id: str, generation: int) -> str:
    """Deterministic opaque token id for safe concurrent refresh retries."""
    message = f"aqlyra-refresh:{session_id}:{generation}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


def refresh_token_jti_hash(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_refresh_token(
    subject: str,
    *,
    token_version: int = 0,
    session_id: str | None = None,
    generation: int = 0,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a fixed-deadline refresh ticket in a server-side session family."""
    now = datetime.now(timezone.utc)
    family_id = session_id or str(uuid.uuid4())
    if type(generation) is not int or generation < 0:
        raise ValueError("Invalid refresh token generation")
    issued = _as_utc_aware(issued_at or now)
    expiry = (
        _as_utc_aware(expires_at)
        if expires_at is not None
        else now + (
            expires_delta
            if expires_delta is not None
            else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
    )
    token_id = refresh_token_jti(family_id, generation)
    return jwt.encode(
        {
            "sub": subject,
            "ver": token_version,
            "type": "refresh",
            "sid": family_id,
            "gen": generation,
            "jti": token_id,
            "iat": issued,
            "exp": expiry,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_refresh_token_claims(token: str) -> tuple[str, int, str, int, str]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type", "ver", "sid", "gen", "jti"]},
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired refresh token") from exc

    subject = payload.get("sub")
    version = payload.get("ver")
    token_type = payload.get("type")
    session_id = payload.get("sid")
    generation = payload.get("gen")
    token_id = payload.get("jti")
    try:
        canonical_session_id = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        canonical_session_id = ""
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or type(version) is not int
        or version < 0
        or token_type != "refresh"
        or canonical_session_id != session_id
        or type(generation) is not int
        or generation < 0
        or not isinstance(token_id, str)
        or not hmac.compare_digest(token_id, refresh_token_jti(session_id, generation))
    ):
        raise InvalidTokenError("Invalid or expired refresh token")
    return subject, version, session_id, generation, token_id


def decode_legacy_refresh_token_claims(
    token: str,
) -> tuple[str, int, str, datetime, datetime]:
    """Decode pre-session-family refresh tokens during a safe one-time upgrade."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type", "ver", "jti"]},
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired refresh token") from exc

    subject = payload.get("sub")
    version = payload.get("ver")
    token_type = payload.get("type")
    token_id = payload.get("jti")
    issued = payload.get("iat")
    expiry = payload.get("exp")
    if (
        "sid" in payload
        or "gen" in payload
        or not isinstance(subject, str)
        or not subject.strip()
        or type(version) is not int
        or version < 0
        or token_type != "refresh"
        or not isinstance(token_id, str)
        or len(token_id) < 20
        or type(issued) not in (int, float)
        or type(expiry) not in (int, float)
    ):
        raise InvalidTokenError("Invalid legacy refresh token")
    try:
        issued_at = datetime.fromtimestamp(issued, timezone.utc).replace(tzinfo=None)
        expires_at = datetime.fromtimestamp(expiry, timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError) as exc:
        raise InvalidTokenError("Invalid legacy refresh token") from exc
    if expires_at <= issued_at:
        raise InvalidTokenError("Invalid legacy refresh token")
    return subject, version, token_id, issued_at, expires_at

def decode_refresh_token_with_version(token: str) -> tuple[str, int]:
    subject, version, _, _, _ = decode_refresh_token_claims(token)
    return subject, version


def decode_access_token_with_version(token: str) -> tuple[str, int]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except JWTError as exc:
        raise InvalidTokenError(
            "Invalid or expired access token",
        ) from exc

    subject = payload.get("sub")
    token_type = payload.get("type")

    if not isinstance(subject, str) or not subject.strip():
        raise InvalidTokenError(
            "Token subject is missing",
        )

    if token_type != "access":
        raise InvalidTokenError(
            "Invalid token type",
        )

    version = payload.get("ver", 0)
    if type(version) is not int or version < 0:
        raise InvalidTokenError("Invalid token version")
    return subject, version


def decode_access_token(token: str) -> str:
    subject, _ = decode_access_token_with_version(token)
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
            options={"require": ["exp", "iat", "sub", "type", "cid"]},
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
        or not subject.strip()
        or not isinstance(challenge_id, str)
        or not challenge_id.strip()
        or token_type != "email_verification"
    ):
        raise InvalidVerificationTokenError(
            "Invalid or expired verification request",
        )

    return subject, challenge_id
