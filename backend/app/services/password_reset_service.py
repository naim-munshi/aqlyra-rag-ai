"""Single-use password recovery OTPs; separate from registration codes."""
from datetime import timedelta
import hashlib
import hmac
import secrets
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.security import hash_password
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.password_reset_code import PasswordResetCode
from app.models.user import User

class PasswordResetError(Exception):
    pass

def _digest(user_id: str, code: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"password-reset:{user_id}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

def issue_password_reset(db: Session, email: str) -> tuple[str, str] | None:
    """Lock the user to serialize parallel requests and prevent code races."""
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None or not user.is_active or user.email_verified_at is None:
        return None
    now = utc_now_naive()
    current = db.get(PasswordResetCode, str(user.id))
    if current is not None and now < current.created_at + timedelta(
        seconds=settings.PASSWORD_RESET_COOLDOWN_SECONDS
    ):
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    if current is None:
        current = PasswordResetCode(user_id=str(user.id))
        db.add(current)
    current.code_digest = _digest(str(user.id), code)
    current.failed_attempts = 0
    current.created_at = now
    current.expires_at = now + timedelta(
        minutes=settings.PASSWORD_RESET_CODE_TTL_MINUTES
    )
    db.commit()
    return user.email, code

def discard_password_reset(db: Session, email: str) -> None:
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is not None:
        current = db.get(PasswordResetCode, str(user.id))
        if current is not None:
            db.delete(current)
            db.commit()

def reset_password(db: Session, email: str, code: str, new_password: str) -> None:
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None or not user.is_active or user.email_verified_at is None:
        raise PasswordResetError("Invalid or expired reset code")
    current = db.get(PasswordResetCode, str(user.id))
    now = utc_now_naive()
    if (
        current is None or current.expires_at <= now
        or current.failed_attempts >= settings.PASSWORD_RESET_MAX_ATTEMPTS
    ):
        raise PasswordResetError("Invalid or expired reset code")
    if not hmac.compare_digest(_digest(str(user.id), code), current.code_digest):
        current.failed_attempts += 1
        if current.failed_attempts >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
            db.delete(current)
        db.commit()
        raise PasswordResetError("Invalid or expired reset code")
    user.hashed_password = hash_password(new_password)
    user.auth_epoch += 1
    db.delete(current)
    db.commit()
