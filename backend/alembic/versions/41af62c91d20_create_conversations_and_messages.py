"""create conversations and messages

Revision ID: 41af62c91d20
Revises: 75c05ee2b51c
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "41af62c91d20"
down_revision: str | None = "75c05ee2b51c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
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
            "title",
            sa.String(length=255),
            server_default="New chat",
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=20),
            server_default="normal",
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
            "mode IN ('normal', 'knowledge')",
            name="ck_conversations_mode",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_conversations_user_updated_at",
        "conversations",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column(
            "id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "provider_name",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "model_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "response_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "citations",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            server_default=sa.text(
                "'[]'::jsonb"
            ),
            nullable=False,
        ),
        sa.Column(
            "is_refusal",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "input_tokens",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "output_tokens",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "evidence_tokens",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_messages_role",
        ),
        sa.CheckConstraint(
            "mode IN ('normal', 'knowledge')",
            name="ck_messages_mode",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL "
            "OR input_tokens >= 0",
            name="ck_messages_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL "
            "OR output_tokens >= 0",
            name="ck_messages_output_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL "
            "OR total_tokens >= 0",
            name="ck_messages_total_tokens",
        ),
        sa.CheckConstraint(
            "evidence_tokens IS NULL "
            "OR evidence_tokens >= 0",
            name="ck_messages_evidence_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_messages_conversation_created_at",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_messages_conversation_created_at",
        table_name="messages",
    )
    op.drop_table("messages")

    op.drop_index(
        "ix_conversations_user_updated_at",
        table_name="conversations",
    )
    op.drop_table("conversations")
