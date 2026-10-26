from datetime import timedelta
from dataclasses import dataclass
import hashlib
import hmac
import math
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.auth.security import hash_password, verify_password
from app.core.datetime_utils import utc_now_naive
from app.models.email_verification_code import (
    EmailVerificationCode,
)
from app.models.user import User


@dataclass(frozen=True)
class IssuedVerificationCode:
    code: str
    challenge_id: str


class VerificationCodeError(Exception):
    """Raised when an email verification code is unusable."""


class VerificationResendTooSoonError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(
            "A new verification code was requested too soon"
        )


def _code_digest(
    *,
    user_id: str,
    code: str,
) -> str:
    message = (
        f"email-verification:{user_id}:{code}"
    ).encode("utf-8")

    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _latest_code(
    db: Session,
    *,
    user_id: str,
) -> EmailVerificationCode | None:
    statement = (
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id
            == user_id,
        )
        .order_by(
            EmailVerificationCode.created_at.desc(),
        )
        .limit(1)
    )

    return db.scalar(statement)


def issue_verification_code(
    db: Session,
    *,
    user: User,
    enforce_cooldown: bool,
) -> IssuedVerificationCode:
    now = utc_now_naive()
    latest = _latest_code(
        db,
        user_id=str(user.id),
    )

    if latest is not None and enforce_cooldown:
        available_at = latest.created_at + timedelta(
            seconds=(
                settings
                .EMAIL_VERIFICATION_RESEND_SECONDS
            ),
        )

        if now < available_at:
            retry_after = math.ceil(
                (available_at - now).total_seconds()
            )
            raise VerificationResendTooSoonError(
                max(1, retry_after)
            )

    active_codes = db.scalars(
        select(EmailVerificationCode).where(
            EmailVerificationCode.user_id
            == str(user.id),
            EmailVerificationCode.consumed_at.is_(None),
        )
    ).all()

    for active_code in active_codes:
        active_code.consumed_at = now

    plain_code = f"{secrets.randbelow(1_000_000):06d}"
    verification_code = EmailVerificationCode(
        user_id=str(user.id),
        code_digest=_code_digest(
            user_id=str(user.id),
            code=plain_code,
        ),
        expires_at=now + timedelta(
            minutes=(
                settings
                .EMAIL_VERIFICATION_CODE_TTL_MINUTES
            ),
        ),
    )

    db.add(verification_code)
    db.flush()
    db.commit()

    return IssuedVerificationCode(
        code=plain_code,
        challenge_id=str(verification_code.id),
    )


def discard_verification_code(
    db: Session,
    *,
    challenge_id: str,
) -> None:
    verification_code = db.scalar(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.id == challenge_id)
        .with_for_update()
    )

    if verification_code is None:
        return

    db.delete(verification_code)
    db.commit()


def verify_email_code(
    db: Session,
    *,
    user_id: str,
    challenge_id: str,
    code: str,
    claim_username: str | None = None,
    claim_password: str | None = None,
    existing_password: str | None = None,
) -> User:
    """Verify ownership and optionally claim a squatted pending account atomically."""
    if (claim_username is None) != (claim_password is None):
        raise VerificationCodeError("Invalid verification claim")
    if claim_username is None and existing_password is None:
        raise VerificationCodeError("Password proof required for verification")
    if claim_username is not None and existing_password is not None:
        raise VerificationCodeError("Cannot mix verification and recovery")
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )

    if user is None or user.email_verified_at is not None or not user.is_active:
        raise VerificationCodeError(
            "Invalid or expired verification code"
        )

    verification_code = db.get(
        EmailVerificationCode,
        challenge_id,
    )
    now = utc_now_naive()

    if (
        verification_code is None
        or verification_code.user_id != str(user.id)
        or verification_code.consumed_at is not None
        or verification_code.expires_at <= now
        or verification_code.failed_attempts
        >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS
    ):
        raise VerificationCodeError(
            "Invalid or expired verification code"
        )

    supplied_digest = _code_digest(
        user_id=str(user.id),
        code=code,
    )

    if not hmac.compare_digest(
        supplied_digest,
        verification_code.code_digest,
    ):
        verification_code.failed_attempts += 1

        if (
            verification_code.failed_attempts
            >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS
        ):
            verification_code.consumed_at = now

        db.commit()
        raise VerificationCodeError(
            "Invalid or expired verification code"
        )

    if claim_username is None and not verify_password(
        existing_password or "", user.hashed_password
    ):
        # Email OTP alone must not activate a squatter-chosen password.
        verification_code.failed_attempts += 1
        if verification_code.failed_attempts >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
            verification_code.consumed_at = now
        db.commit()
        raise VerificationCodeError("Invalid or expired verification code")

    if claim_username is not None and claim_password is not None:
        username = claim_username.strip().lower()
        # The email OTP—not account possession—authorizes this recovery.
        # Do not overwrite credentials until mailbox ownership is proven.
        duplicate_username = db.scalar(
            select(User.id).where(
                User.username == username,
                User.id != str(user.id),
            )
        )
        if duplicate_username is not None:
            raise VerificationCodeError("Requested username is unavailable")
        user.username = username
        user.hashed_password = hash_password(claim_password)
        user.auth_epoch += 1

    verification_code.consumed_at = now
    user.email_verified_at = now
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise VerificationCodeError("Requested username is unavailable") from exc
    db.refresh(user)

    return user
