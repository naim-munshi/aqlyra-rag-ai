"""Opt-in, bounded recovery for already parsed legacy cloud Knowledge files.

The model is instantiated lazily, only after a real owner-linked ready file
needs embeddings. No remote object is read or modified; the existing verified
chunks are reembedded in a transaction and existing vectors are preserved.
"""
import logging
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.embeddings.registry import create_configured_embedding_provider
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.services.embedding_reindex_service import reindex_document_embeddings


logger = logging.getLogger(__name__)


def backfill_ready_semantic_embeddings(
    *, db: Session, limit: int = 1,
) -> int:
    if not settings.KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP:
        return 0
    if settings.EMBEDDING_PROVIDER != "local_onnx":
        logger.warning("knowledge_semantic_backfill status=SKIPPED reason=provider")
        return 0
    if not 1 <= limit <= 3:
        raise ValueError("Semantic backfill limit must be 1..3")
    provider = create_configured_embedding_provider()
    info = provider.info
    indexed = exists(
        select(EmbeddingRecord.id)
        .join(DocumentChunk, DocumentChunk.id == EmbeddingRecord.chunk_id)
        .where(
            DocumentChunk.document_id == Document.id,
            EmbeddingRecord.provider_name == info.provider_name,
            EmbeddingRecord.model_name == info.model_name,
            EmbeddingRecord.dimension == 384,
        )
    )
    eligible = list(db.scalars(
        select(Document)
        .join(
            CloudUploadIntent,
            (CloudUploadIntent.document_id == Document.id)
            & (CloudUploadIntent.user_id == Document.user_id),
        )
        .where(
            Document.status == "ready",
            Document.storage_path.like("cloud://%"),
            CloudUploadIntent.status == "completed",
            Document.file_extension.in_(
                (".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv")
            ),
            ~indexed,
        )
        .order_by(Document.created_at, Document.id)
        .limit(limit)
    ).all())
    processed = 0
    for doc in eligible:
        try:
            result = reindex_document_embeddings(
                db=db, document=doc, provider=provider,
            )
            if result.created_count > 0:
                processed += 1
                logger.info(
                    "knowledge_semantic_backfill status=PASS chunks=%s",
                    result.created_count,
                )
        except Exception as exc:
            db.rollback()
            logger.warning(
                "knowledge_semantic_backfill status=FAIL error_type=%s",
                type(exc).__name__,
            )
    return processed
