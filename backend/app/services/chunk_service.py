from sqlalchemy.orm import Session

from app.chunking import (
    ChunkSource,
    build_chunks,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_unit import DocumentUnit


class ChunkHierarchyError(Exception):
    """Raised when a generated chunk references an invalid parent."""


def create_document_chunks(
    db: Session,
    document: Document,
    units: list[DocumentUnit],
) -> list[DocumentChunk]:
    for unit in units:
        if unit.document_id != document.id:
            raise ValueError(
                "Document unit does not belong "
                "to the supplied document"
            )

        if unit.id is None:
            raise ValueError(
                "Document units must be flushed "
                "before chunk generation"
            )

    sources = [
        ChunkSource(
            document_id=document.id,
            document_label=(
                document.original_filename
            ),
            unit_id=unit.id,
            unit_index=unit.unit_index,
            unit_type=unit.unit_type,
            source_label=unit.source_label,
            content=unit.content,
            metadata=dict(
                unit.unit_metadata or {}
            ),
        )
        for unit in units
    ]

    chunk_drafts = build_chunks(
        sources
    )

    chunk_models: dict[
        str,
        DocumentChunk,
    ] = {}

    for draft in chunk_drafts:
        chunk_models[draft.id] = (
            DocumentChunk(
                id=draft.id,
                document_id=(
                    draft.document_id
                ),
                document_unit_id=(
                    draft.document_unit_id
                ),
                chunk_index=(
                    draft.chunk_index
                ),
                chunk_level=(
                    draft.chunk_level
                ),
                chunk_role=(
                    draft.chunk_role
                ),
                source_label=(
                    draft.source_label
                ),
                section_path=list(
                    draft.section_path
                ),
                content=draft.content,
                embedding_content=(
                    draft.embedding_content
                ),
                content_hash=(
                    draft.content_hash
                ),
                token_count=(
                    draft.token_count
                ),
                char_count=(
                    draft.char_count
                ),
                word_count=(
                    draft.word_count
                ),
                start_char=(
                    draft.start_char
                ),
                end_char=draft.end_char,
                start_page=(
                    draft.start_page
                ),
                end_page=draft.end_page,
                strategy_version=(
                    draft.strategy_version
                ),
                chunk_metadata=dict(
                    draft.metadata
                ),
            )
        )

    for draft in chunk_drafts:
        if draft.parent_chunk_id is None:
            continue

        parent_chunk = chunk_models.get(
            draft.parent_chunk_id
        )

        if parent_chunk is None:
            raise ChunkHierarchyError(
                "Generated chunk references "
                "an unknown parent"
            )

        chunk_models[draft.id].parent = (
            parent_chunk
        )

    chunks = [
        chunk_models[draft.id]
        for draft in chunk_drafts
    ]

    db.add_all(chunks)

    return chunks
