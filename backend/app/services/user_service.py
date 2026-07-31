from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    hash_password,
    verify_password,
)
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


def create_user(
    db: Session,
    user_data: UserCreate,
) -> User:
    normalized_email = str(user_data.email).strip().lower()
    normalized_username = user_data.username.strip().lower()

    if get_user_by_email(db, normalized_email):
        raise DuplicateUserError("email")

    if get_user_by_username(db, normalized_username):
        raise DuplicateUserError("username")

    user = User(
        username=normalized_username,
        email=normalized_email,
        hashed_password=hash_password(
            user_data.password,
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