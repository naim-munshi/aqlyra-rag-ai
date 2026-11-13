"""Read-only, tenant-scoped detection of usable current semantic vectors.

The API may have parsed a valid document while its separate free-tier
semantic worker was sleeping, throttled, or unavailable. Before making a
remote query-embedding request, check if there are any actually usable
vectors for this owner's selected retrieval scope. No source content,
document metadata, or cross-owner counts leave PostgreSQL.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.remote_semantic_provider import MODEL
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.retrieval.types import RetrievalQuery
from app.services.retrieval_exclusions import permitted_retrieval_document


def scope_has_current_dense_vectors(
    *, db: Session, query: RetrievalQuery,
) -> bool:
    """One bounded EXISTS; never count or embed another owner's chunks."""
    statement = (
        select(EmbeddingRecord.id)
        .join(DocumentChunk, DocumentChunk.id == EmbeddingRecord.chunk_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.user_id == query.user_id,
            Document.status == "ready",
            permitted_retrieval_document(),
            EmbeddingRecord.provider_name == "remote_onnx",
            EmbeddingRecord.model_name == MODEL,
            EmbeddingRecord.dimension == 384,
            EmbeddingRecord.content_hash == DocumentChunk.content_hash,
        )
    )
    if query.document_ids:
        statement = statement.where(Document.id.in_(query.document_ids))
    if query.chunk_roles:
        statement = statement.where(DocumentChunk.chunk_role.in_(query.chunk_roles))
    return bool(db.scalar(select(statement.exists())))
