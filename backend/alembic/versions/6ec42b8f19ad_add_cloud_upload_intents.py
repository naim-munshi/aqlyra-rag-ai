"""Add durable single-use cloud upload intents without changing RAG data.

Revision ID: 6ec42b8f19ad
Revises: f18a3c42e917
"""
from alembic import op
import sqlalchemy as sa

revision = "6ec42b8f19ad"
down_revision = "f18a3c42e917"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloud_upload_intents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("object_key", sa.String(length=250), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("expected_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=16),
            nullable=False, server_default="issued",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('issued', 'claimed', 'completed', 'failed')",
            name="ck_cloud_upload_intents_status",
        ),
        sa.CheckConstraint(
            "expected_size > 0 AND expected_size <= 26214400",
            name="ck_cloud_upload_intents_size",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "object_key", name="uq_cloud_upload_intents_object_key",
        ),
    )
    op.create_index(
        "ix_cloud_upload_intents_owner_status_expiry",
        "cloud_upload_intents", ["user_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_cloud_upload_intents_created_at",
        "cloud_upload_intents", ["created_at"],
    )


def downgrade() -> None:
    # Destructive rollback is NOT part of production deployment. Only an
    # operator-approved backup/restore procedure may remove this table.
    op.drop_index(
        "ix_cloud_upload_intents_created_at",
        table_name="cloud_upload_intents",
    )
    op.drop_index(
        "ix_cloud_upload_intents_owner_status_expiry",
        table_name="cloud_upload_intents",
    )
    op.drop_table("cloud_upload_intents")
