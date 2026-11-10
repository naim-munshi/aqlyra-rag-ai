"""Opt-in, bounded recovery for already parsed legacy cloud Knowledge files.

The model is instantiated lazily, only after a real owner-linked ready file
needs embeddings. No remote object is read or modified; the existing verified
chunks are reembedded in a transaction and existing vectors are preserved.
"""
import logging
import time
from sqlalchemy import exists, literal, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.embeddings.registry import create_configured_embedding_provider
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.services.embedding_reindex_service import reindex_missing_document_embeddings
from app.services.retrieval_exclusions import permitted_retrieval_document


logger = logging.getLogger(__name__)


def backfill_ready_semantic_embeddings(
    *, db: Session, limit: int = 1,
) -> int:
    if not settings.KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP:
        return 0
    if settings.EMBEDDING_PROVIDER != "remote_onnx":
        logger.warning("knowledge_semantic_backfill status=SKIPPED reason=provider")
        return 0
    target = settings.KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID.strip()
    if settings.APP_ENV.strip().lower() == "production" and not target:
        logger.warning(
            "knowledge_semantic_backfill status=SKIPPED reason=target_required"
        )
        return 0
    if not 1 <= limit <= 3:
        raise ValueError("Semantic backfill limit must be 1..3")
    batch_chunks = settings.KNOWLEDGE_SEMANTIC_BACKFILL_MAX_CHUNKS
    max_batches = settings.KNOWLEDGE_SEMANTIC_BACKFILL_MAX_BATCHES
    if batch_chunks * max_batches > 64:
        raise ValueError("Semantic backfill exceeds 64 chunks per targeted run")
    provider = create_configured_embedding_provider()
    info = provider.info
    # A single embedding row is NOT proof that a whole document is indexed.
    # Check each chunk for a current 384D vector from the configured model
    # with the matching content hash; missing and stale rows both need repair.
    current_vector = exists(
        select(EmbeddingRecord.id).where(
            EmbeddingRecord.chunk_id == DocumentChunk.id,
            EmbeddingRecord.provider_name == info.provider_name,
            EmbeddingRecord.model_name == info.model_name,
            EmbeddingRecord.dimension == 384,
            EmbeddingRecord.content_hash == DocumentChunk.content_hash,
        )
    )
    needs_repair = exists(
        select(DocumentChunk.id).where(
            DocumentChunk.document_id == Document.id,
            ~current_vector,
        )
    )
    statement = (
        select(Document)
        .join(
            CloudUploadIntent,
            (CloudUploadIntent.document_id == Document.id)
            & (CloudUploadIntent.user_id == Document.user_id),
        )
        .where(
            Document.status == "ready",
            permitted_retrieval_document(),
            Document.storage_path.like("cloud://%"),
            CloudUploadIntent.status == "completed",
            # A completed intent is not proof of this exact file unless the
            # immutable finalized key and byte-level metadata still agree.
            # Never re-index a deleted, remapped or inconsistent upload.
            CloudUploadIntent.deleted_at.is_(None),
            CloudUploadIntent.final_object_key.is_not(None),
            Document.storage_path == literal("cloud://") + CloudUploadIntent.final_object_key,
            Document.checksum_sha256 == CloudUploadIntent.expected_sha256,
            Document.file_size == CloudUploadIntent.expected_size,
            Document.file_extension.in_(
                (".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv")
            ),
            needs_repair,
        )
        .order_by(Document.created_at, Document.id)
        .limit(limit)
    )
    if target:
        statement = statement.where(Document.id == target)
    eligible = list(db.scalars(statement).all())
    processed = 0
    for doc in eligible:
        created_for_document = 0
        for batch_index in range(max_batches):
            try:
                # This implementation commits each small batch independently.
                # A restart, quota failure or free-tier spin-down resumes by
                # finding missing/stale content hashes, not an in-memory cursor.
                result = reindex_missing_document_embeddings(
                    db=db, document=doc, provider=provider,
                    max_chunks=batch_chunks,
                )
                if result.created_count == 0:
                    break
                created_for_document += result.created_count
                logger.info(
                    "knowledge_semantic_backfill status=PASS chunks=%s batch=%s",
                    result.created_count, batch_index + 1,
                )
                if result.created_count < batch_chunks:
                    break
                if batch_index + 1 < max_batches:
                    time.sleep(1.0)
            except Exception as exc:
                # Stop this document on any failure, especially 429: never
                # amplify provider quotas with the remaining planned batches.
                db.rollback()
                logger.warning(
                    "knowledge_semantic_backfill status=FAIL error_type=%s",
                    type(exc).__name__,
                )
                break
        if created_for_document:
            processed += 1
    return processed
