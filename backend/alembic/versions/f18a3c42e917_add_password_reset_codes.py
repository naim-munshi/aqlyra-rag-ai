"""add password reset challenges and session-revocation counter

Revision ID: f18a3c42e917
Revises: e7a9c3d5f1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "f18a3c42e917"
down_revision = "e7a9c3d5f1b2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column(
        "auth_epoch", sa.Integer(), nullable=False, server_default="0"
    ))
    op.create_table(
        "password_reset_codes",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

def downgrade() -> None:
    op.drop_table("password_reset_codes")
    op.drop_column("users", "auth_epoch")
