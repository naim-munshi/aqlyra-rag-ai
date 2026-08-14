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
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
)

if TYPE_CHECKING:
    from app.models.memory import Memory


class MemoryEmbedding(Base):
    """
    Replaceable vector index for one personal memory.

    Deleting or rebuilding this record must never delete
    the authoritative Memory.content.
    """

    __tablename__ = "memory_embeddings"

    __table_args__ = (
        CheckConstraint(
            f"dimension = {EMBEDDING_DIMENSION}",
            name="ck_memory_embeddings_dimension",
        ),
        CheckConstraint(
            "input_token_count >= 0",
            name="ck_memory_embeddings_token_count",
        ),
        CheckConstraint(
            "estimated_cost_usd >= 0",
            name="ck_memory_embeddings_cost",
        ),
        UniqueConstraint(
            "memory_id",
            "provider_name",
            "model_name",
            name=(
                "uq_memory_embeddings_"
                "memory_provider_model"
            ),
        ),
        Index(
            "ix_memory_embeddings_provider_model",
            "provider_name",
            "model_name",
        ),
        Index(
            "ix_memory_embeddings_embedding_hnsw",
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

    memory_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "memories.id",
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

    embedding_metadata: Mapped[
        dict[str, Any]
    ] = mapped_column(
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

    memory: Mapped["Memory"] = relationship(
        back_populates="embeddings",
    )
