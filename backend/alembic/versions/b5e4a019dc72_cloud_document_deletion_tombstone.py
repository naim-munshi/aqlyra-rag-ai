"""Track confirmed cloud document deletion before delayed staging sweep.

Revision ID: b5e4a019dc72
Revises: a7c60d4e21bb

Only the new cloud_upload_intents ledger changes. No RAG, vector, user,
document, or conversation tables are modified. Rehearse on a disposable
staging database with a verified backup before running migrations.
"""
from alembic import op
import sqlalchemy as sa

revision = "b5e4a019dc72"
down_revision = "a7c60d4e21bb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cloud_upload_intents",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # Never downgrade an environment holding real uploaded documents
    # without a reviewed backup and independent restore rehearsal.
    op.drop_column("cloud_upload_intents", "deleted_at")
