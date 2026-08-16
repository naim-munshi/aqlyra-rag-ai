"""add pinned conversations

Revision ID: c2f4e8a91b6d
Revises: 8a7c2d91f4e6
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c2f4e8a91b6d"
down_revision: str | None = (
    "8a7c2d91f4e6"
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_index(
        "ix_conversations_user_pinned_updated_at",
        "conversations",
        [
            "user_id",
            "is_pinned",
            "updated_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_user_pinned_updated_at",
        table_name="conversations",
    )

    op.drop_column(
        "conversations",
        "is_pinned",
    )
