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
    from app.models.document_unit import DocumentUnit
    from app.models.embedding_record import EmbeddingRecord


class DocumentChunk(Base):
    """
    Searchable knowledge chunk generated from a document unit.

    Supports:
    - Adaptive content chunks
    - Parent-child hierarchy
    - RAPTOR-style summary nodes
    - Atomic proposition nodes
    - Citation and source metadata
    """

    __tablename__ = "document_chunks"

    __table_args__ = (
        CheckConstraint(
            "chunk_role IN "
            "('content', 'summary', 'proposition')",
            name="ck_document_chunks_role",
        ),
        CheckConstraint(
            "chunk_level >= 0",
            name="ck_document_chunks_level",
        ),
        CheckConstraint(
            "token_count >= 0 "
            "AND char_count >= 0 "
            "AND word_count >= 0",
            name="ck_document_chunks_counts",
        ),
        CheckConstraint(
            "("
            "start_char IS NULL "
            "AND end_char IS NULL"
            ") OR ("
            "start_char >= 0 "
            "AND end_char >= start_char"
            ")",
            name="ck_document_chunks_character_range",
        ),
        CheckConstraint(
            "("
            "start_page IS NULL "
            "AND end_page IS NULL"
            ") OR ("
            "start_page >= 1 "
            "AND end_page >= start_page"
            ")",
            name="ck_document_chunks_page_range",
        ),
        UniqueConstraint(
            "document_id",
            "strategy_version",
            "chunk_index",
            name="uq_document_chunks_strategy_index",
        ),
        Index(
            "ix_document_chunks_document_strategy_role",
            "document_id",
            "strategy_version",
            "chunk_role",
        ),
        Index(
            "ix_document_chunks_document_unit",
            "document_id",
            "document_unit_id",
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

    document_unit_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey(
            "document_units.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    parent_chunk_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey(
            "document_chunks.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    chunk_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    chunk_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="content",
        server_default="content",
        index=True,
    )

    source_label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    section_path: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    start_char: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_char: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    start_page: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_page: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    strategy_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="iahc-x-v1",
        server_default="iahc-x-v1",
    )

    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
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
        back_populates="chunks",
    )

    unit: Mapped["DocumentUnit | None"] = relationship(
        back_populates="chunks",
    )

    parent: Mapped["DocumentChunk | None"] = relationship(
        "DocumentChunk",
        remote_side="DocumentChunk.id",
        back_populates="children",
    )

    children: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="parent",
        passive_deletes=True,
    )

    embedding_records: Mapped[
        list["EmbeddingRecord"]
    ] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "EmbeddingRecord.provider_name, "
            "EmbeddingRecord.model_name"
        ),
    )
