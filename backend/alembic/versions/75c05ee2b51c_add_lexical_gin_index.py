"""add lexical gin index

Revision ID: 75c05ee2b51c
Revises: dd2595cf2740
"""

from typing import Sequence, Union

from alembic import op


revision: str = "75c05ee2b51c"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "dd2595cf2740"

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


INDEX_NAME = (
    "ix_document_chunks_embedding_content_fts"
)


def upgrade() -> None:
    """Add GIN index for lexical full-text retrieval."""

    op.execute(
        f"""
        CREATE INDEX {INDEX_NAME}
        ON document_chunks
        USING gin (
            to_tsvector(
                'simple'::regconfig,
                embedding_content
            )
        )
        """
    )


def downgrade() -> None:
    """Remove lexical full-text GIN index."""

    op.execute(
        f"""
        DROP INDEX IF EXISTS {INDEX_NAME}
        """
    )
