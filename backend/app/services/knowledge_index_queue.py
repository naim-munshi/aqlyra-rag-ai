"""Persistent, tenant-safe document indexing using existing Document.status.

No new database table, broker or fragile in-memory job list. A queued
document survives process shutdown. PostgreSQL SKIP LOCKED provides the
atomic claim; the content always comes from the verified private object.
"""
from __future__ import annotations

import logging
import threading
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.database.connection import SessionLocal
from app.models.document import Document
from app.models.cloud_upload_intent import CloudUploadIntent
from app.services.cloud_process_io import cloud_processing_source
from app.services.document_processing_service import process_document

log = logging.getLogger(__name__)
INDEXABLE_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv",
})
_RECLAIM_AFTER = timedelta(minutes=30)


def should_index(extension: str) -> bool:
    return extension.lower() in INDEXABLE_EXTENSIONS


def enqueue_document(
    *, db: Session, owner_id: str, document_id: str,
) -> Document | None:
    """Owner-scoped retry/queue; never discard the previous file or chunks."""
    if not settings.KNOWLEDGE_AUTO_INDEX_ENABLED:
        return None
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == owner_id,
        ).with_for_update()
    )
    if document is None:
        return None
    if not should_index(document.file_extension):
        return document
    if document.status in ("uploaded", "failed"):
        document.status = "queued"
        document.error_message = None
        db.commit()
        db.refresh(document)
    return document


def requeue_verified_legacy_cloud_documents(
    db: Session, *, limit: int = 10,
) -> int:
    """One-shot operator recovery of old durable uploads, never local files.

    Only completed owner-matched upload intents qualify. The subsequent
    worker verifies immutable cloud bytes and checksum before parsing.
    No file deletion, ownership changes, or reprocessing of ready files.
    """
    if not settings.KNOWLEDGE_AUTO_INDEX_ENABLED:
        return 0
    if not settings.PRIVATE_OBJECT_STORAGE_ENABLED:
        return 0
    if not 1 <= limit <= 25:
        raise ValueError("Backfill batch limit must be 1..25")
    try:
        documents = list(db.scalars(
            select(Document)
            .join(
                CloudUploadIntent,
                (CloudUploadIntent.document_id == Document.id)
                & (CloudUploadIntent.user_id == Document.user_id),
            )
            .where(
                CloudUploadIntent.status == "completed",
                Document.status == "uploaded",
                Document.storage_path.like("cloud://%"),
                Document.file_extension.in_(tuple(INDEXABLE_EXTENSIONS)),
            )
            .order_by(Document.created_at, Document.id)
            .limit(limit)
            .with_for_update(of=Document, skip_locked=True)
        ).all())
        for document in documents:
            document.status = "queued"
            document.error_message = None
        db.commit()
        log.info(
            "knowledge_legacy_cloud_backfill queued=%s", len(documents)
        )
        return len(documents)
    except Exception:
        db.rollback()
        raise


def claim_next_document(db: Session) -> str | None:
    """Atomically claim one queued row across any number of app workers."""
    statement = (
        select(Document)
        .where(
            Document.status == "queued",
            Document.file_extension.in_(tuple(INDEXABLE_EXTENSIONS)),
        )
        .order_by(Document.created_at, Document.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    try:
        document = db.scalar(statement)
        if document is None:
            db.rollback()
            return None
        document.status = "processing"
        document.error_message = None
        db.commit()
        return document.id
    except Exception:
        db.rollback()
        raise


def reclaim_stale_processing(db: Session) -> int:
    """Recover interrupted jobs only after sufficient time to avoid overlap."""
    threshold = utc_now_naive() - _RECLAIM_AFTER
    try:
        result = db.execute(
            update(Document)
            .where(
                Document.status == "processing",
                Document.updated_at < threshold,
                Document.file_extension.in_(tuple(INDEXABLE_EXTENSIONS)),
            )
            .values(status="queued")
        )
        count = result.rowcount or 0
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise


def run_one_index_job() -> bool:
    """One short-lived DB session per job; no user files survive on disk."""
    with SessionLocal() as db:
        document_id = claim_next_document(db)
    if document_id is None:
        return False
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None or doc.status != "processing":
            return True
        try:
            if doc.storage_path.startswith("cloud://"):
                with cloud_processing_source(
                    db=db, owner_id=doc.user_id, document=doc,
                ) as source:
                    process_document(
                        db=db, document=doc,
                        verified_source_path=source, claimed_for_worker=True,
                    )
            else:
                process_document(db=db, document=doc, claimed_for_worker=True)
            log.info("knowledge_index_complete doc_id=%s", document_id)
        except Exception as exc:
            # Cloud byte verification may fail BEFORE process_document is
            # invoked. Mark those failures explicitly; the safe owner
            # retry endpoint can queue the preserved original again.
            db.rollback()
            current = db.get(Document, document_id)
            if current is not None and current.status == "processing":
                current.status = "failed"
                current.error_message = type(exc).__name__[:120]
                db.commit()
            log.warning(
                "knowledge_index_failed doc_id=%s error_type=%s",
                document_id, type(exc).__name__,
            )
    return True


class KnowledgeIndexWorker:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not settings.KNOWLEDGE_AUTO_INDEX_ENABLED:
            return
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="aqlyra-knowledge-index",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        # Reclaim stale work every 30 minutes, not every poll.
        last_reclaim = None
        while not self._stop.is_set():
            try:
                now = utc_now_naive()
                if last_reclaim is None or now - last_reclaim > timedelta(minutes=30):
                    with SessionLocal() as db:
                        reclaim_stale_processing(db)
                    last_reclaim = now
                if run_one_index_job():
                    continue
            except Exception as exc:
                log.warning("knowledge_worker_unavailable error_type=%s",
                            type(exc).__name__)
            self._stop.wait(settings.KNOWLEDGE_INDEX_POLL_SECONDS)
