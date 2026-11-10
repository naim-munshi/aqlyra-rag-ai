"""Opt-in, bounded recovery for already parsed legacy cloud Knowledge files.

The model is instantiated lazily, only after a real owner-linked ready file
needs embeddings. No remote object is read or modified; the existing verified
chunks are reembedded in a transaction and existing vectors are preserved.
"""
import logging
import time
from dataclasses import dataclass
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


@dataclass
class BackfillProgress:
    """Local only: report bounded-pass progress without exposing owner data."""
    created_chunks: int = 0
    failed: bool = False


def backfill_ready_semantic_embeddings(
    *, db: Session, limit: int = 1,
    progress: BackfillProgress | None = None,
) -> int:
    if not settings.KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP:
        return 0
    if settings.EMBEDDING_PROVIDER != "remote_onnx":
        logger.warning("knowledge_semantic_backfill status=SKIPPED reason=provider")
        return 0
    target = settings.KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID.strip()
    if (
        settings.APP_ENV.strip().lower() == "production"
        and not target
        and not settings.KNOWLEDGE_SEMANTIC_BACKFILL_ALL_VERIFIED_ENABLED
    ):
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
    remaining_batches = max_batches
    stop_on_error = False
    for doc in eligible:
        if remaining_batches <= 0 or stop_on_error:
            break
        created_for_document = 0
        for batch_index in range(max_batches):
            if remaining_batches <= 0:
                break
            # The 64-chunk limit is GLOBAL across selected documents, not
            # 64 per document when an operator selects up to three.
            remaining_batches -= 1
            try:
                # This implementation commits each small batch independently.
                # A restart or quota failure resumes by current content hashes.
                result = reindex_missing_document_embeddings(
                    db=db, document=doc, provider=provider,
                    max_chunks=batch_chunks,
                )
                if result.created_count == 0:
                    break
                created_for_document += result.created_count
                if progress is not None:
                    progress.created_chunks += result.created_count
                logger.info(
                    "knowledge_semantic_backfill status=PASS chunks=%s batch=%s",
                    result.created_count, max_batches - remaining_batches,
                )
                if result.created_count < batch_chunks:
                    break
                if remaining_batches > 0:
                    time.sleep(1.0)
            except Exception as exc:
                # Never continue to OTHER documents after a 429 or any
                # provider failure; no repeated quota storms on cold start.
                db.rollback()
                logger.warning(
                    "knowledge_semantic_backfill status=FAIL error_type=%s",
                    type(exc).__name__,
                )
                stop_on_error = True
                if progress is not None:
                    progress.failed = True
                break
        if created_for_document:
            processed += 1
    return processed


# This is a deliberately explicit operator recovery, not an always-on
# scheduler. It uses the existing verified-intent scan, commits in 8-chunk
# batches, and NEVER changes the 64-chunk-per-pass ceiling. Repeated passes
# happen only with a second, default-off campaign switch. Stop immediately
# on provider failure rather than retrying a quota or transport outage.
_CAMPAIGN_MAX_CHUNKS = 1024
_CAMPAIGN_MAX_PASSES = 24


def run_verified_semantic_recovery_campaign(*, db: Session) -> int:
    if not (
        settings.KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP
        and settings.KNOWLEDGE_SEMANTIC_RECOVERY_CAMPAIGN_ENABLED
    ):
        return 0
    if (
        settings.APP_ENV.strip().lower() == "production"
        and not settings.KNOWLEDGE_SEMANTIC_BACKFILL_ALL_VERIFIED_ENABLED
    ):
        logger.warning("knowledge_semantic_campaign status=SKIPPED reason=verified_opt_in")
        return 0
    if settings.KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID.strip():
        logger.warning("knowledge_semantic_campaign status=SKIPPED reason=target_conflict")
        return 0
    per_pass = (
        settings.KNOWLEDGE_SEMANTIC_BACKFILL_MAX_CHUNKS
        * settings.KNOWLEDGE_SEMANTIC_BACKFILL_MAX_BATCHES
    )
    if not 1 <= per_pass <= 64:
        raise ValueError("Campaign requires the existing <=64 chunk pass limit")
    max_passes = min(_CAMPAIGN_MAX_PASSES, _CAMPAIGN_MAX_CHUNKS // per_pass)
    created_total = 0
    for number in range(1, max_passes + 1):
        progress = BackfillProgress()
        processed = backfill_ready_semantic_embeddings(
            db=db, limit=3, progress=progress,
        )
        created_total += progress.created_chunks
        logger.info(
            "knowledge_semantic_campaign status=PROGRESS pass=%d created=%d total=%d",
            number, progress.created_chunks, created_total,
        )
        if progress.failed:
            logger.warning(
                "knowledge_semantic_campaign status=STOP reason=provider_failure total=%d",
                created_total,
            )
            return created_total
        if processed == 0 or progress.created_chunks == 0:
            logger.info(
                "knowledge_semantic_campaign status=COMPLETE total=%d", created_total,
            )
            return created_total
        if number < max_passes:
            time.sleep(3.0)
    logger.warning(
        "knowledge_semantic_campaign status=BUDGET_REACHED total=%d",
        created_total,
    )
    return created_total
