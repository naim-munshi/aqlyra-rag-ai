from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


def test_document_chunks_table_exists(
    db_session: Session,
) -> None:
    inspector = inspect(
        db_session.get_bind()
    )

    assert inspector.has_table(
        "document_chunks"
    )


def test_document_chunk_model_has_required_fields() -> None:
    column_names = {
        column.name
        for column in DocumentChunk.__table__.columns
    }

    required_columns = {
        "id",
        "document_id",
        "document_unit_id",
        "parent_chunk_id",
        "chunk_index",
        "chunk_level",
        "chunk_role",
        "source_label",
        "section_path",
        "content",
        "embedding_content",
        "content_hash",
        "token_count",
        "char_count",
        "word_count",
        "start_char",
        "end_char",
        "start_page",
        "end_page",
        "strategy_version",
        "chunk_metadata",
        "created_at",
        "updated_at",
    }

    assert required_columns.issubset(
        column_names
    )


def test_document_chunk_unique_constraint_exists() -> None:
    constraint_names = {
        constraint.name
        for constraint
        in DocumentChunk.__table__.constraints
    }

    assert (
        "uq_document_chunks_strategy_index"
        in constraint_names
    )
