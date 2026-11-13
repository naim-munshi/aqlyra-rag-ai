"""Add opt-in structured study fit facts without touching legacy user journeys.

Revision ID: 0bd6703bf8a4
Revises: d4ec2f9b7860

The existing private records stay intact. Deployment order:
apply this additive migration, then deploy the new API/UI.
"""
from alembic import op
import sqlalchemy as sa

revision = "0bd6703bf8a4"
down_revision = "d4ec2f9b7860"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "study_cases",
        sa.Column("applicant_facts", sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'")),
    )
    op.add_column(
        "study_universities",
        sa.Column("requirements", sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    # Protect private applicant facts from accidental destructive downgrades.
    raise RuntimeError("Study match columns contain private data; restore from backup only")
