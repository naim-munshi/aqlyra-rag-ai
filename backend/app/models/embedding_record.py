from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


EMBEDDING_DIMENSION = 384


if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk


class EmbeddingRecord(Base):
    """
    Vector representation of one document chunk.

    One chunk can later have embeddings from multiple
    providers or models without changing the chunk itself.
    """

    __tablename__ = "embedding_records"

    __table_args__ = (
        CheckConstraint(
            f"dimension = {EMBEDDING_DIMENSION}",
            name="ck_embedding_records_dimension",
        ),
        CheckConstraint(
            "input_token_count >= 0",
            name="ck_embedding_records_token_count",
        ),
        CheckConstraint(
            "estimated_cost_usd >= 0",
            name="ck_embedding_records_cost",
        ),
        UniqueConstraint(
            "chunk_id",
            "provider_name",
            "model_name",
            name="uq_embedding_records_chunk_provider_model",
        ),
        Index(
            "ix_embedding_records_provider_model",
            "provider_name",
            "model_name",
        ),
        Index(
            "ix_embedding_records_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={
                "m": 16,
                "ef_construction": 64,
            },
            postgresql_ops={
                "embedding": "vector_cosine_ops",
            },
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    chunk_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "document_chunks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    provider_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=EMBEDDING_DIMENSION,
        server_default=str(
            EMBEDDING_DIMENSION
        ),
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    input_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    estimated_cost_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    embedding_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    chunk: Mapped["DocumentChunk"] = relationship(
        back_populates="embedding_records",
    )
