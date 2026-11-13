"""Add staging-object cleanup marker to the new isolated intent table.

Revision ID: a7c60d4e21bb
Revises: 9ce7a58d230f
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c60d4e21bb"
down_revision = "9ce7a58d230f"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("cloud_upload_intents",
                  sa.Column("stage_deleted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_cloud_upload_intents_stage_cleanup",
                    "cloud_upload_intents", ["status", "expires_at"])

def downgrade() -> None:
    # Apply only to disposable databases after backup/review.
    op.drop_index("ix_cloud_upload_intents_stage_cleanup",
                  table_name="cloud_upload_intents")
    op.drop_column("cloud_upload_intents", "stage_deleted_at")
