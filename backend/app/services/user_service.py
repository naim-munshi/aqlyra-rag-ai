import hashlib
import re
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    hash_password,
    verify_password,
)
from app.core.datetime_utils import utc_now_naive
from app.models.user import User
from app.schemas.user import UserCreate


class DuplicateUserError(Exception):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(
            f"A user with this {field} already exists",
        )


def get_user_by_id(
    db: Session,
    user_id: str,
) -> User | None:
    statement = select(User).where(
        User.id == user_id,
    )

    return db.scalar(statement)


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = select(User).where(
        User.email == email,
    )

    return db.scalar(statement)


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    statement = select(User).where(
        User.username == username,
    )

    return db.scalar(statement)


def get_user_by_google_subject(
    db: Session,
    google_subject: str,
) -> User | None:
    statement = select(User).where(
        User.google_subject == google_subject,
    )

    return db.scalar(statement)


def create_user(
    db: Session,
    user_data: UserCreate,
    *,
    email_verified: bool,
) -> User:
    normalized_email = str(user_data.email).strip().lower()
    normalized_username = user_data.username.strip().lower()

    existing_email_user = get_user_by_email(
        db,
        normalized_email,
    )

    if existing_email_user is not None:
        if (
            not email_verified
            and existing_email_user.email_verified_at is None
        ):
            username_owner = get_user_by_username(
                db,
                normalized_username,
            )

            if (
                username_owner is not None
                and username_owner.id
                != existing_email_user.id
            ):
                raise DuplicateUserError("username")

            existing_email_user.username = (
                normalized_username
            )
            existing_email_user.hashed_password = (
                hash_password(user_data.password)
            )

            try:
                db.commit()
                db.refresh(existing_email_user)
            except IntegrityError as exc:
                db.rollback()
                raise DuplicateUserError(
                    "email or username",
                ) from exc

            return existing_email_user

        raise DuplicateUserError("email")

    if get_user_by_username(db, normalized_username):
        raise DuplicateUserError("username")

    user = User(
        username=normalized_username,
        email=normalized_email,
        hashed_password=hash_password(
            user_data.password,
        ),
        email_verified_at=(
            utc_now_naive()
            if email_verified
            else None
        ),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()

        raise DuplicateUserError(
            "email or username",
        ) from exc

    return user


def _google_username(
    db: Session,
    *,
    email: str,
    subject: str,
) -> str:
    local_part = email.partition("@")[0]
    base = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        local_part,
    ).strip("_-").lower()
    base = base or "google_user"

    if len(base) < 3:
        base = f"{base}_user"

    suffix = hashlib.sha256(
        subject.encode("utf-8")
    ).hexdigest()[:8]

    for number in range(100):
        ending = (
            f"_{suffix}"
            if number == 0
            else f"_{suffix}_{number}"
        )
        candidate = (
            base[: 50 - len(ending)]
            + ending
        )

        if get_user_by_username(db, candidate) is None:
            return candidate

    raise RuntimeError(
        "Unable to allocate a unique Google username"
    )


def get_or_create_google_user(
    db: Session,
    *,
    google_subject: str,
    email: str,
) -> User:
    user = get_user_by_google_subject(
        db,
        google_subject,
    )

    if user is not None:
        return user

    user = get_user_by_email(
        db,
        email,
    )

    if user is not None:
        if (
            user.google_subject is not None
            and user.google_subject != google_subject
        ):
            raise DuplicateUserError(
                "Google account"
            )

        if user.email_verified_at is None:
            user.username = _google_username(
                db,
                email=email,
                subject=google_subject,
            )
            user.hashed_password = hash_password(
                secrets.token_urlsafe(48)
            )

        user.google_subject = google_subject
        user.email_verified_at = utc_now_naive()

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError as exc:
            db.rollback()
            raise DuplicateUserError(
                "Google account"
            ) from exc

        return user

    user = User(
        username=_google_username(
            db,
            email=email,
            subject=google_subject,
        ),
        email=email,
        hashed_password=hash_password(
            secrets.token_urlsafe(48)
        ),
        email_verified_at=utc_now_naive(),
        google_subject=google_subject,
    )
    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateUserError(
            "email or Google account"
        ) from exc

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    normalized_email = email.strip().lower()

    user = get_user_by_email(
        db,
        normalized_email,
    )

    if user is None:
        return None

    if not verify_password(
        password,
        user.hashed_password,
    ):
        return None

    return user
