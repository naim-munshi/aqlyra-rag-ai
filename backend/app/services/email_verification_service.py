from datetime import timedelta
from dataclasses import dataclass
import hashlib
import hmac
import math
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
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
    verification_code = db.get(
        EmailVerificationCode,
        challenge_id,
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
) -> User:
    user = db.get(
        User,
        user_id,
    )

    if user is None or user.email_verified_at is not None:
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

    verification_code.consumed_at = now
    user.email_verified_at = now
    db.commit()
    db.refresh(user)

    return user
