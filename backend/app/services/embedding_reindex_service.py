from dataclasses import dataclass

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.services.embedding_service import (
    create_chunk_embeddings,
)


class DocumentNotReadyForEmbeddingError(Exception):
    """Raised when a document is not ready for embedding."""


class DocumentChunksNotFoundError(Exception):
    """Raised when a processed document has no chunks."""


@dataclass(frozen=True, slots=True)
class EmbeddingReindexResult:
    document_id: str
    provider_name: str
    model_name: str
    dimension: int
    chunk_count: int
    replaced_count: int
    created_count: int


def reindex_document_embeddings(
    db: Session,
    document: Document,
    provider: EmbeddingProvider | None = None,
) -> EmbeddingReindexResult:
    if document.status != "ready":
        raise DocumentNotReadyForEmbeddingError(
            "Document must be ready before "
            "embeddings can be rebuilt"
        )

    active_provider = (
        provider
        or create_configured_embedding_provider()
    )

    provider_info = active_provider.info

    chunks_statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document.id
        )
        .order_by(
            DocumentChunk.chunk_index.asc(),
            DocumentChunk.id.asc(),
        )
    )

    chunks = list(
        db.scalars(
            chunks_statement
        ).all()
    )

    if not chunks:
        raise DocumentChunksNotFoundError(
            "No document chunks are available "
            "for embedding"
        )

    existing_count_statement = (
        select(func.count())
        .select_from(EmbeddingRecord)
        .join(
            DocumentChunk,
            DocumentChunk.id
            == EmbeddingRecord.chunk_id,
        )
        .where(
            DocumentChunk.document_id
            == document.id,
            EmbeddingRecord.provider_name
            == provider_info.provider_name,
            EmbeddingRecord.model_name
            == provider_info.model_name,
        )
    )

    replaced_count = (
        db.scalar(
            existing_count_statement
        )
        or 0
    )

    try:
        records = create_chunk_embeddings(
            db=db,
            chunks=chunks,
            provider=active_provider,
        )

        db.flush()
        db.commit()

    except Exception:
        db.rollback()
        raise

    return EmbeddingReindexResult(
        document_id=document.id,
        provider_name=(
            provider_info.provider_name
        ),
        model_name=provider_info.model_name,
        dimension=provider_info.dimension,
        chunk_count=len(chunks),
        replaced_count=replaced_count,
        created_count=len(records),
    )



def reindex_missing_document_embeddings(
    *, db: Session, document: Document,
    provider: EmbeddingProvider | None = None,
    max_chunks: int = 8,
) -> EmbeddingReindexResult:
    """Repair only missing/stale current-model vectors in a bounded transaction.

    Unlike a full rebuild, this operator never rewrites complete vectors. Each
    successful invocation commits at most 24 chunks; repeated invocations
    resume from the next missing chunk with no cursor or shared state.
    """
    if document.status != "ready":
        raise DocumentNotReadyForEmbeddingError(
            "Document must be ready before embeddings can be rebuilt"
        )
    if not 1 <= max_chunks <= 24:
        raise ValueError("Incremental embedding batch must be 1..24 chunks")
    active_provider = provider or create_configured_embedding_provider()
    info = active_provider.info
    current = exists(
        select(EmbeddingRecord.id).where(
            EmbeddingRecord.chunk_id == DocumentChunk.id,
            EmbeddingRecord.provider_name == info.provider_name,
            EmbeddingRecord.model_name == info.model_name,
            EmbeddingRecord.dimension == info.dimension,
            EmbeddingRecord.content_hash == DocumentChunk.content_hash,
        )
    )
    statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document.id,
            ~current,
        )
        .order_by(DocumentChunk.chunk_index, DocumentChunk.id)
        .limit(max_chunks)
    )
    chunks = list(db.scalars(statement).all())
    if not chunks:
        return EmbeddingReindexResult(
            document_id=document.id,
            provider_name=info.provider_name,
            model_name=info.model_name,
            dimension=info.dimension,
            chunk_count=0,
            replaced_count=0,
            created_count=0,
        )
    identifiers = [chunk.id for chunk in chunks]
    stale_count = db.scalar(
        select(func.count(EmbeddingRecord.id)).where(
            EmbeddingRecord.chunk_id.in_(identifiers),
            EmbeddingRecord.provider_name == info.provider_name,
            EmbeddingRecord.model_name == info.model_name,
        )
    ) or 0
    try:
        records = create_chunk_embeddings(
            db=db,
            chunks=chunks,
            provider=active_provider,
        )
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return EmbeddingReindexResult(
        document_id=document.id,
        provider_name=info.provider_name,
        model_name=info.model_name,
        dimension=info.dimension,
        chunk_count=len(chunks),
        replaced_count=stale_count,
        created_count=len(records),
    )
