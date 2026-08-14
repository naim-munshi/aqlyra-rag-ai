from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.memory_embedding import (
        MemoryEmbedding,
    )
    from app.models.message import Message
    from app.models.user import User


class Memory(Base):
    """
    Aqlyra-owned long-term personal memory.

    Memory text is authoritative. Vector embeddings are
    replaceable retrieval indexes stored separately.
    """

    __tablename__ = "memories"

    __table_args__ = (
        CheckConstraint(
            (
                "kind IN "
                "('fact', 'preference', 'goal', 'decision')"
            ),
            name="ck_memories_kind",
        ),
        CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_memories_importance",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_memories_confidence",
        ),
        Index(
            "ix_memories_user_active_updated_at",
            "user_id",
            "is_active",
            "updated_at",
        ),
        Index(
            "ix_memories_user_kind",
            "user_id",
            "kind",
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

    kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    normalized_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    importance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        server_default="0.5",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
    )

    source_message_id: Mapped[
        str | None
    ] = mapped_column(
        String,
        ForeignKey(
            "messages.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )

    owner: Mapped["User"] = relationship(
        back_populates="memories",
    )

    source_message: Mapped[
        "Message | None"
    ] = relationship(
        back_populates="extracted_memories",
    )

    embeddings: Mapped[
        list["MemoryEmbedding"]
    ] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "MemoryEmbedding.provider_name, "
            "MemoryEmbedding.model_name"
        ),
    )
