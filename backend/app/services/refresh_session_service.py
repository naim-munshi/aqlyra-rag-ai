"""Database-backed refresh token rotation and reuse detection."""
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.security import create_refresh_token, refresh_token_jti, refresh_token_jti_hash
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.refresh_session import RefreshSession
from app.models.user import User

REFRESH_REUSE_GRACE_SECONDS = 30


class InvalidRefreshSessionError(Exception):
    """Refresh ticket is unknown, expired, revoked, or no longer current."""


class RefreshTokenReplayError(InvalidRefreshSessionError):
    """A consumed refresh ticket was reused outside the concurrency grace window."""


@dataclass(frozen=True, slots=True)
class RotatedRefreshSession:
    user: User
    session: RefreshSession


def _new_session_row(*, user, session_id, generation, issued_at, expires_at):
    token_id = refresh_token_jti(session_id, generation)
    return RefreshSession(
        session_id=session_id,
        generation=generation,
        user_id=str(user.id),
        jti_hash=refresh_token_jti_hash(token_id),
        issued_at=issued_at,
        expires_at=expires_at,
    )


def _token_for(user: User, session: RefreshSession) -> str:
    return create_refresh_token(
        subject=str(user.id),
        token_version=user.auth_epoch,
        session_id=session.session_id,
        generation=session.generation,
        issued_at=session.issued_at,
        expires_at=session.expires_at,
    )


def create_refresh_session(db: Session, user: User) -> str:
    now = utc_now_naive()
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session_id = str(uuid4())
    record = _new_session_row(
        user=user, session_id=session_id, generation=0,
        issued_at=now, expires_at=expires_at,
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _token_for(user, record)


def rotate_refresh_session(
    db: Session,
    *,
    user_id: str,
    token_version: int,
    session_id: str,
    generation: int,
    token_id: str,
) -> RotatedRefreshSession:
    """Rotate once; concurrent retries receive the exact same successor.

    Reuse outside the grace window revokes all refresh families and
    increments auth_epoch, invalidating already-issued access tokens.
    """
    now = utc_now_naive()
    # Lock user before session so logout and refresh use a consistent lock order.
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or not user.is_active or user.auth_epoch != token_version:
        db.rollback()
        raise InvalidRefreshSessionError("Refresh session is no longer valid")

    record = db.scalar(
        select(RefreshSession)
        .where(
            RefreshSession.session_id == session_id,
            RefreshSession.generation == generation,
        )
        .with_for_update()
    )
    if (
        record is None
        or record.user_id != user_id
        or record.jti_hash != refresh_token_jti_hash(token_id)
        or record.revoked_at is not None
        or record.expires_at <= now
    ):
        db.rollback()
        raise InvalidRefreshSessionError("Refresh session is no longer valid")

    if record.consumed_at is not None:
        age = (now - record.consumed_at).total_seconds()
        successor = db.scalar(
            select(RefreshSession)
            .where(
                RefreshSession.session_id == session_id,
                RefreshSession.generation == generation + 1,
            )
            .with_for_update()
        )
        if (
            0 <= age <= REFRESH_REUSE_GRACE_SECONDS
            and successor is not None
            and successor.user_id == user_id
            and successor.revoked_at is None
            and successor.consumed_at is None
            and successor.expires_at == record.expires_at
            and successor.expires_at > now
        ):
            db.commit()
            return RotatedRefreshSession(user=user, session=successor)

        db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        user.auth_epoch += 1
        db.commit()
        raise RefreshTokenReplayError("Refresh token reuse detected")

    record.consumed_at = now
    successor = _new_session_row(
        user=user, session_id=session_id, generation=generation + 1,
        issued_at=now, expires_at=record.expires_at,
    )
    db.add(successor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return RotatedRefreshSession(user=user, session=successor)
