"""Track final cloud object ownership and atomic Document linkage.

Revision ID: 9ce7a58d230f
Revises: 6ec42b8f19ad

Additive migration: alters only the new cloud_upload_intents table.
The documents/pgvector/chunks schema is unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "9ce7a58d230f"
down_revision = "6ec42b8f19ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cloud_upload_intents",
        sa.Column("final_object_key", sa.String(length=250), nullable=True),
    )
    op.add_column(
        "cloud_upload_intents",
        sa.Column("document_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cloud_upload_intents_document_id",
        "cloud_upload_intents",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_cloud_upload_intents_final_object_key",
        "cloud_upload_intents",
        ["final_object_key"],
    )
    op.create_unique_constraint(
        "uq_cloud_upload_intents_document_id",
        "cloud_upload_intents",
        ["document_id"],
    )
    op.create_index(
        "ix_cloud_upload_intents_recovery",
        "cloud_upload_intents",
        ["status", "claimed_at"],
    )


def downgrade() -> None:
    # Destructive rollback requires explicit owner approval and backups.
    op.drop_index(
        "ix_cloud_upload_intents_recovery",
        table_name="cloud_upload_intents",
    )
    op.drop_constraint(
        "uq_cloud_upload_intents_document_id",
        "cloud_upload_intents",
        type_="unique",
    )
    op.drop_constraint(
        "uq_cloud_upload_intents_final_object_key",
        "cloud_upload_intents",
        type_="unique",
    )
    op.drop_constraint(
        "fk_cloud_upload_intents_document_id",
        "cloud_upload_intents",
        type_="foreignkey",
    )
    op.drop_column("cloud_upload_intents", "document_id")
    op.drop_column("cloud_upload_intents", "final_object_key")
