"""create embedding records with vector index

Revision ID: dd2595cf2740
Revises: b3cae84f1c71
Create Date: 2026-08-03 02:07:59.358218
"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "dd2595cf2740"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b3cae84f1c71"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    """Create vector embedding storage and indexes."""

    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    op.create_table(
        "embedding_records",
        sa.Column(
            "id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "provider_name",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "model_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "dimension",
            sa.Integer(),
            server_default="384",
            nullable=False,
        ),
        sa.Column(
            "embedding",
            VECTOR(384),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "input_token_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "estimated_cost_usd",
            sa.Float(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "embedding_metadata",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'{}'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dimension = 384",
            name=(
                "ck_embedding_records_"
                "dimension"
            ),
        ),
        sa.CheckConstraint(
            "estimated_cost_usd >= 0",
            name=(
                "ck_embedding_records_cost"
            ),
        ),
        sa.CheckConstraint(
            "input_token_count >= 0",
            name=(
                "ck_embedding_records_"
                "token_count"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "chunk_id",
            "provider_name",
            "model_name",
            name=(
                "uq_embedding_records_"
                "chunk_provider_model"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_embedding_records_chunk_id"
        ),
        "embedding_records",
        ["chunk_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_embedding_records_content_hash"
        ),
        "embedding_records",
        ["content_hash"],
        unique=False,
    )

    op.create_index(
        "ix_embedding_records_provider_model",
        "embedding_records",
        [
            "provider_name",
            "model_name",
        ],
        unique=False,
    )

    op.create_index(
        "ix_embedding_records_embedding_hnsw",
        "embedding_records",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={
            "m": 16,
            "ef_construction": 64,
        },
        postgresql_ops={
            "embedding": (
                "vector_cosine_ops"
            ),
        },
    )


def downgrade() -> None:
    """Remove vector embedding storage."""

    op.drop_index(
        "ix_embedding_records_embedding_hnsw",
        table_name="embedding_records",
    )

    op.drop_index(
        "ix_embedding_records_provider_model",
        table_name="embedding_records",
    )

    op.drop_index(
        op.f(
            "ix_embedding_records_content_hash"
        ),
        table_name="embedding_records",
    )

    op.drop_index(
        op.f(
            "ix_embedding_records_chunk_id"
        ),
        table_name="embedding_records",
    )

    op.drop_table(
        "embedding_records"
    )
