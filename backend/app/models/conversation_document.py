from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.document import Document


class ConversationDocument(Base):
    __tablename__ = "conversation_documents"

    __table_args__ = (
        Index(
            "ix_conversation_documents_conversation_created_at",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_conversation_documents_document_id",
            "document_id",
        ),
    )

    conversation_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now_naive,
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="document_links",
    )

    document: Mapped["Document"] = relationship(
        back_populates="conversation_links",
    )
