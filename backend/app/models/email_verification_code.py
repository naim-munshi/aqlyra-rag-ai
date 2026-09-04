from datetime import datetime
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"
    __table_args__ = (
        Index(
            "ix_email_verification_codes_user_created_at",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    code_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    consumed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
    )
