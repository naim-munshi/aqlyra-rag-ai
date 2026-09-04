from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.document import Document
    from app.models.memory import Memory
    from app.models.project import Project


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    email_verified_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime,
        nullable=True,
    )

    google_subject: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    conversations: Mapped[
        list["Conversation"]
    ] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    memories: Mapped[list["Memory"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
