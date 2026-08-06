from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk


class DocumentUnit(Base):
    """
    A structured source unit extracted from a document.

    Examples:
    - PDF page
    - PowerPoint slide
    - Excel worksheet
    - DOCX section
    - TXT/Markdown segment
    """

    __tablename__ = "document_units"

    __table_args__ = (
        CheckConstraint(
            "unit_type IN "
            "('page', 'slide', 'sheet', 'section', 'text')",
            name="ck_document_units_type",
        ),
        UniqueConstraint(
            "document_id",
            "unit_index",
            name="uq_document_units_document_index",
        ),
        Index(
            "ix_document_units_document_type",
            "document_id",
            "unit_type",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    source_label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    unit_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
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

    document: Mapped["Document"] = relationship(
        back_populates="units",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )
