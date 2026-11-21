"""create server-side refresh token session families

Revision ID: a1f8c6d2e904
Revises: f18a3c42e917
"""
from alembic import op
import sqlalchemy as sa

revision = "a1f8c6d2e904"
down_revision = "f18a3c42e917"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_sessions",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "generation"),
        sa.UniqueConstraint("jti_hash", name="uq_refresh_sessions_jti_hash"),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_user_expires", "refresh_sessions", ["user_id", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_sessions_user_expires", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
