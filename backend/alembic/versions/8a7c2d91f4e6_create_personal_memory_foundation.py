"""create personal memory foundation

Revision ID: 8a7c2d91f4e6
Revises: 41af62c91d20
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8a7c2d91f4e6"
down_revision: str | None = "41af62c91d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    op.create_table(
        "memories",
        sa.Column(
            "id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "normalized_content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "importance",
            sa.Float(),
            server_default="0.5",
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column(
            "source_message_id",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
            (
                "kind IN "
                "('fact', 'preference', "
                "'goal', 'decision')"
            ),
            name="ck_memories_kind",
        ),
        sa.CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_memories_importance",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_memories_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_memories_source_message_id",
        "memories",
        ["source_message_id"],
        unique=False,
    )

    op.create_index(
        "ix_memories_user_active_updated_at",
        "memories",
        [
            "user_id",
            "is_active",
            "updated_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_memories_user_kind",
        "memories",
        ["user_id", "kind"],
        unique=False,
    )

    op.create_table(
        "memory_embeddings",
        sa.Column(
            "id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "memory_id",
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
            name="ck_memory_embeddings_dimension",
        ),
        sa.CheckConstraint(
            "input_token_count >= 0",
            name="ck_memory_embeddings_token_count",
        ),
        sa.CheckConstraint(
            "estimated_cost_usd >= 0",
            name="ck_memory_embeddings_cost",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "memory_id",
            "provider_name",
            "model_name",
            name=(
                "uq_memory_embeddings_"
                "memory_provider_model"
            ),
        ),
    )

    op.create_index(
        "ix_memory_embeddings_memory_id",
        "memory_embeddings",
        ["memory_id"],
        unique=False,
    )

    op.create_index(
        "ix_memory_embeddings_content_hash",
        "memory_embeddings",
        ["content_hash"],
        unique=False,
    )

    op.create_index(
        "ix_memory_embeddings_provider_model",
        "memory_embeddings",
        [
            "provider_name",
            "model_name",
        ],
        unique=False,
    )

    op.create_index(
        "ix_memory_embeddings_embedding_hnsw",
        "memory_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={
            "m": 16,
            "ef_construction": 64,
        },
        postgresql_ops={
            "embedding": "vector_cosine_ops",
        },
    )


def downgrade() -> None:
    op.drop_index(
        "ix_memory_embeddings_embedding_hnsw",
        table_name="memory_embeddings",
    )

    op.drop_index(
        "ix_memory_embeddings_provider_model",
        table_name="memory_embeddings",
    )

    op.drop_index(
        "ix_memory_embeddings_content_hash",
        table_name="memory_embeddings",
    )

    op.drop_index(
        "ix_memory_embeddings_memory_id",
        table_name="memory_embeddings",
    )

    op.drop_table("memory_embeddings")

    op.drop_index(
        "ix_memories_user_kind",
        table_name="memories",
    )

    op.drop_index(
        "ix_memories_user_active_updated_at",
        table_name="memories",
    )

    op.drop_index(
        "ix_memories_source_message_id",
        table_name="memories",
    )

    op.drop_table("memories")
