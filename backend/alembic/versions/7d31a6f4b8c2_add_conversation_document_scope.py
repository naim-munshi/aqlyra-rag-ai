"""add conversation document scope

Revision ID: 7d31a6f4b8c2
Revises: c2f4e8a91b6d
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d31a6f4b8c2"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "c2f4e8a91b6d"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "conversation_documents",
        sa.Column(
            "conversation_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id",
            "document_id",
        ),
    )

    op.create_index(
        "ix_conversation_documents_conversation_created_at",
        "conversation_documents",
        [
            "conversation_id",
            "created_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_conversation_documents_document_id",
        "conversation_documents",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_documents_document_id",
        table_name="conversation_documents",
    )

    op.drop_index(
        "ix_conversation_documents_conversation_created_at",
        table_name="conversation_documents",
    )

    op.drop_table(
        "conversation_documents"
    )
