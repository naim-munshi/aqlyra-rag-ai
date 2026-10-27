"""Bounded, operator-only staging object cleanup. Never touches final keys."""
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from app.config.settings import Settings, settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.services.private_object_storage import (
    PrivateObjectStorageError, _client, assert_owned_key,
)

@dataclass(frozen=True)
class CleanupSummary:
    eligible: int
    deleted: int
    failed: int

def cleanup_stale_staging(
    *, db: Session, cfg: Settings = settings, store=None,
    dry_run: bool = True, grace_seconds: int = 3600, limit: int = 20,
) -> CleanupSummary:
    """Only completed or unclaimed expired intents are safe to sweep.

    Claimed and failed intents may need recovery or manual investigation.
    Final keys are never accepted by assert_owned_key. Uses row locks
    and records completion only after a confirmed remote delete.
    """
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    if not 3600 <= grace_seconds <= 604800 or not 1 <= limit <= 50:
        raise ValueError("Cleanup bounds are invalid")
    cutoff = utc_now_naive() - timedelta(seconds=grace_seconds)
    # An "issued" label with a final key is inconsistent too.
    # A "completed" label alone does not prove a durable final object
    # binding. Keep inconsistent rows for reconciliation, never GC them.
    eligible_state = or_(
        and_(
            CloudUploadIntent.status == "issued",
            CloudUploadIntent.final_object_key.is_(None),
            CloudUploadIntent.document_id.is_(None),
        ),
        and_(
            CloudUploadIntent.status == "completed",
            CloudUploadIntent.final_object_key.is_not(None),
            CloudUploadIntent.document_id.is_not(None),
        ),
    )
    ids = list(db.scalars(
        select(CloudUploadIntent.id).where(
            eligible_state,
            CloudUploadIntent.expires_at < cutoff,
            CloudUploadIntent.stage_deleted_at.is_(None),
        ).order_by(CloudUploadIntent.expires_at, CloudUploadIntent.id).limit(limit)
    ).all())
    db.rollback()
    if dry_run:
        return CleanupSummary(eligible=len(ids), deleted=0, failed=0)
    client = store if store is not None else _client(cfg)
    removed = failures = 0
    for row_id in ids:
        try:
            record = db.scalar(
                select(CloudUploadIntent).where(
                    CloudUploadIntent.id == row_id,
                    eligible_state,
                    CloudUploadIntent.expires_at < cutoff,
                    CloudUploadIntent.stage_deleted_at.is_(None),
                ).with_for_update(skip_locked=True)
            )
            if record is None:
                db.rollback()
                continue
            assert_owned_key(owner_id=record.user_id, key=record.object_key)
            client.delete_object(
                Bucket=cfg.OBJECT_STORAGE_BUCKET, Key=record.object_key,
            )
            record.stage_deleted_at = utc_now_naive()
            db.commit()
            removed += 1
        except Exception:
            db.rollback()
            failures += 1
    return CleanupSummary(eligible=len(ids), deleted=removed, failed=failures)
