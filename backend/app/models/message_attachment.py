from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.message import Message


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "document_id",
            name="uq_message_attachments_message_document",
        ),
        Index(
            "ix_message_attachments_message_position",
            "message_id",
            "position",
        ),
        Index(
            "ix_message_attachments_document_id",
            "document_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    message_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
    )

    message: Mapped["Message"] = relationship(
        back_populates="attachments",
    )

    document: Mapped["Document"] = relationship(
        back_populates="message_attachment_links",
    )
