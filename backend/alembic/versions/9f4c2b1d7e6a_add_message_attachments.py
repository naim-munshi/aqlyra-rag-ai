"""add message attachments

Revision ID: 9f4c2b1d7e6a
Revises: 7d31a6f4b8c2
Create Date: 2026-08-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4c2b1d7e6a"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "7d31a6f4b8c2"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_attachments",
        sa.Column(
            "id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "document_id",
            name=(
                "uq_message_attachments_"
                "message_document"
            ),
        ),
    )

    op.create_index(
        "ix_message_attachments_message_position",
        "message_attachments",
        ["message_id", "position"],
        unique=False,
    )

    op.create_index(
        "ix_message_attachments_document_id",
        "message_attachments",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_message_attachments_document_id",
        table_name="message_attachments",
    )

    op.drop_index(
        "ix_message_attachments_message_position",
        table_name="message_attachments",
    )

    op.drop_table(
        "message_attachments"
    )
