"""PRIVATE cloud upload -> Document DB integration, not exposed as an API.

The owner-bound upload intent stores its final key *before* remote writes.
The final object is independently verified, then Document+intent state
are committed atomically. A retry can safely link a previously verified
final object after a process crash, without reissuing a write grant.

This module is deliberately NOT connected to existing document routes.
Users must retain the current persistent local storage until cloud
download, parsing, deletion and orphan GC all pass acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import Settings, settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.user import User
from app.services.cloud_upload_intent_service import _verified_owner
from app.services.private_object_promotion import (
    PromotedPrivateObject,
    assert_owned_final_key,
    final_object_key,
    promote_verified_private_upload,
    verify_existing_final_private_object,
)
from app.services.private_object_storage import (
    PrivateObjectStorageError,
    assert_owned_key,
)

# Retain stale records for human/operator review. No automatic remote deletion.
RECOVERY_GRACE_SECONDS = 300


class CloudFinalizationConflict(PrivateObjectStorageError):
    """Owner's intent was used, expired, missing or no longer claimable."""


@dataclass(frozen=True)
class FinalizationResult:
    document_id: str
    final_object_key: str
    recovered: bool


def _valid_intent_id(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def claim_with_reserved_final_key(
    *, db: Session, owner: User, intent_id: str,
    cfg: Settings = settings,
) -> CloudUploadIntent | None:
    """Atomic CAS from issued to claimed, persisting a unique final key."""
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    owner_id = _verified_owner(owner)
    if not _valid_intent_id(intent_id):
        return None

    now = utc_now_naive()
    # Used only for deriving type from a *stored*, owner-scoped stage key.
    candidate = db.scalar(
        select(CloudUploadIntent)
        .where(
            CloudUploadIntent.id == intent_id,
            CloudUploadIntent.user_id == owner_id,
            CloudUploadIntent.status == "issued",
            CloudUploadIntent.expires_at > now,
        )
    )
    if candidate is None:
        db.rollback()
        return None
    ext = assert_owned_key(owner_id=owner_id, key=candidate.object_key)
    final_key = final_object_key(
        owner_id=owner_id, object_id=str(uuid4()), extension=ext,
    )
    try:
        updated_id = db.scalar(
            update(CloudUploadIntent)
            .where(
                CloudUploadIntent.id == intent_id,
                CloudUploadIntent.user_id == owner_id,
                CloudUploadIntent.status == "issued",
                CloudUploadIntent.expires_at > now,
                CloudUploadIntent.final_object_key.is_(None),
                CloudUploadIntent.document_id.is_(None),
            )
            .values(
                status="claimed",
                claimed_at=now,
                final_object_key=final_key,
            )
            .returning(CloudUploadIntent.id)
        )
        if updated_id is None:
            db.rollback()
            return None
        db.commit()
        return db.get(CloudUploadIntent, updated_id)
    except Exception:
        db.rollback()
        raise


def _claimed_intent_for_owner(
    *, db: Session, owner: User, intent_id: str,
) -> CloudUploadIntent | None:
    owner_id = _verified_owner(owner)
    if not _valid_intent_id(intent_id):
        return None
    result = db.scalar(
        select(CloudUploadIntent)
        .where(
            CloudUploadIntent.id == intent_id,
            CloudUploadIntent.user_id == owner_id,
            CloudUploadIntent.status == "claimed",
            CloudUploadIntent.final_object_key.is_not(None),
            CloudUploadIntent.document_id.is_(None),
        )
    )
    if result is None:
        db.rollback()
    return result


def commit_verified_cloud_document(
    *, db: Session, owner: User, intent_id: str,
    cfg: Settings = settings, client=None,
) -> FinalizationResult:
    """Reverify immutable final bytes, atomically create Document+mapping.

    S3 object writes and SQL transaction cannot share a transaction.
    A failed/unknown DB commit must *never* trigger deletion of the
    already-promoted object, which can be reconciled from the intent.
    """
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    pending = _claimed_intent_for_owner(db=db, owner=owner, intent_id=intent_id)
    if pending is None or pending.final_object_key is None:
        raise CloudFinalizationConflict("Cloud upload intent is not claimable")
    owner_id = _verified_owner(owner)
    final_key = pending.final_object_key

    # Complete cryptographic verification BEFORE creating any Document.
    verified = verify_existing_final_private_object(
        owner_id=owner_id,
        final_key=final_key,
        expected_size=pending.expected_size,
        expected_sha256=pending.expected_sha256,
        cfg=cfg,
        client=client,
    )
    if verified.content_type != pending.content_type:
        raise PrivateObjectStorageError("Cloud document type mismatch")

    # Close the prior read transaction before acquiring the write lock.
    db.rollback()
    try:
        intent = db.scalar(
            select(CloudUploadIntent)
            .where(
                CloudUploadIntent.id == intent_id,
                CloudUploadIntent.user_id == owner_id,
            )
            .with_for_update()
        )
        if (
            intent is None
            or intent.status != "claimed"
            or intent.document_id is not None
            or intent.final_object_key != verified.key
            or intent.expected_sha256 != verified.sha256
            or intent.expected_size != verified.size_bytes
            or intent.content_type != verified.content_type
        ):
            raise CloudFinalizationConflict("Cloud upload intent changed")

        # RAG duplicate-content contract remains identical to local uploads.
        duplicate = db.scalar(
            select(Document.id)
            .where(
                Document.user_id == owner_id,
                Document.checksum_sha256 == verified.sha256,
            )
        )
        if duplicate:
            raise CloudFinalizationConflict("Document content already exists")

        extension = assert_owned_final_key(
            owner_id=owner_id, key=verified.key,
        )
        document_id = str(uuid4())
        document = Document(
            id=document_id,
            user_id=owner_id,
            original_filename=intent.original_filename,
            stored_filename=verified.key.rsplit("/", 1)[-1],
            # Strong namespace distinguishes object references from local
            # paths; existing local handlers must NOT parse cloud:// paths.
            storage_path="cloud://" + verified.key,
            content_type=verified.content_type,
            file_extension=extension,
            file_size=verified.size_bytes,
            checksum_sha256=verified.sha256,
            status="uploaded",
            requires_ocr=False,
        )
        db.add(document)
        # Force the referenced row's INSERT before setting the foreign key.
        # This is only a FLUSH: Document and intent still commit atomically.
        db.flush()
        intent.status = "completed"
        intent.completed_at = utc_now_naive()
        intent.document_id = document_id
        db.commit()
        return FinalizationResult(
            document_id=document_id,
            final_object_key=verified.key,
            recovered=False,
        )
    except (IntegrityError, CloudFinalizationConflict):
        db.rollback()
        raise
    except Exception:
        # Network/DB ambiguous commits MUST retain a recoverable final key.
        db.rollback()
        raise


def finalize_cloud_upload(
    *, db: Session, owner: User, intent_id: str,
    cfg: Settings = settings, client=None,
) -> FinalizationResult:
    """Orchestrate claim, verified promotion, and atomic DB linkage.

    A remote or DB failure intentionally leaves the claimed record for
    explicit owner-scoped recovery; no public route calls this function.
    """
    intent = claim_with_reserved_final_key(
        db=db, owner=owner, intent_id=intent_id, cfg=cfg,
    )
    if intent is None or intent.final_object_key is None:
        raise CloudFinalizationConflict("Cloud upload intent is unavailable")
    promoted = promote_verified_private_upload(
        owner_id=_verified_owner(owner),
        staging_key=intent.object_key,
        expected_size=intent.expected_size,
        expected_sha256=intent.expected_sha256,
        final_key=intent.final_object_key,
        cfg=cfg,
        client=client,
    )
    if promoted.key != intent.final_object_key:
        raise PrivateObjectStorageError("Final object reference mismatch")
    return commit_verified_cloud_document(
        db=db, owner=owner, intent_id=intent_id, cfg=cfg, client=client,
    )


def recover_promoted_cloud_document(
    *, db: Session, owner: User, intent_id: str,
    cfg: Settings = settings, client=None,
) -> FinalizationResult:
    """Recover after crash *only when* final object re-verifies.

    No replayed presigned PUT grant or blind object deletion is performed.
    """
    result = commit_verified_cloud_document(
        db=db, owner=owner, intent_id=intent_id, cfg=cfg, client=client,
    )
    return FinalizationResult(
        document_id=result.document_id,
        final_object_key=result.final_object_key,
        recovered=True,
    )


def list_stale_claimed_uploads(
    *, db: Session, older_than_seconds: int = RECOVERY_GRACE_SECONDS,
    limit: int = 50,
) -> list[CloudUploadIntent]:
    """Internal read-only operator discovery for a future locked GC worker.

    This is never user-facing and deliberately performs no remote deletes.
    """
    if not 60 <= older_than_seconds <= 86400 or not 1 <= limit <= 100:
        raise ValueError("Invalid recovery scan bounds")
    cutoff = utc_now_naive() - timedelta(seconds=older_than_seconds)
    return list(db.scalars(
        select(CloudUploadIntent)
        .where(
            CloudUploadIntent.status == "claimed",
            CloudUploadIntent.final_object_key.is_not(None),
            CloudUploadIntent.claimed_at < cutoff,
        )
        .order_by(CloudUploadIntent.claimed_at, CloudUploadIntent.id)
        .limit(limit)
    ).all())
