"""Internal durable upload-intent lifecycle, not a public upload endpoint.

Creating an intent stores no signing secrets. Atomic owner-scoped state
transitions enforce single-use claims, even with concurrent API workers.
The completion caller must *first* verify bytes, promote the object to a
key with no outstanding write grant and persist the Document metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config.settings import Settings, settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.user import User
from app.services.private_object_storage import (
    PrivateObjectStorageError,
    UploadGrant,
    prepare_private_upload,
)
from app.services.storage_service import _sanitize_original_filename

_INTENT_TTL_SECONDS = 900
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReservedUpload:
    intent_id: str
    expires_at: datetime
    grant: UploadGrant


def _verified_owner(owner: User) -> str:
    if not owner.is_active or owner.email_verified_at is None:
        raise PrivateObjectStorageError("Verified account required")
    try:
        canonical = str(UUID(owner.id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PrivateObjectStorageError("Invalid owner identifier") from exc
    if canonical != owner.id:
        raise PrivateObjectStorageError("Invalid owner identifier")
    return canonical


def reserve_upload_intent(
    *, db: Session, owner: User, original_filename: str,
    expected_size: int, expected_sha256: str,
    cfg: Settings = settings, client=None,
) -> ReservedUpload:
    """Reserve signed staging key and save owner-bound, expiring upload intent.

    Nothing becomes user-visible until the database commit succeeds.
    """
    owner_id = _verified_owner(owner)
    if not _HEX_SHA256.fullmatch(expected_sha256):
        raise PrivateObjectStorageError("Invalid SHA-256 digest")
    filename = _sanitize_original_filename(original_filename)
    grant = prepare_private_upload(
        owner_id=owner_id, filename=filename,
        size_bytes=expected_size, cfg=cfg, client=client,
    )
    now = utc_now_naive()
    intent = CloudUploadIntent(
        user_id=owner_id, object_key=grant.key,
        original_filename=filename,
        content_type=grant.content_type,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
        status="issued",
        created_at=now,
        expires_at=now + timedelta(seconds=_INTENT_TTL_SECONDS),
    )
    db.add(intent)
    try:
        db.commit()
        db.refresh(intent)
    except Exception:
        db.rollback()
        raise
    return ReservedUpload(
        intent_id=intent.id, expires_at=intent.expires_at, grant=grant,
    )


def _transition(
    *, db: Session, owner: User, intent_id: str,
    expected: str, target: str, expiry_required: bool,
) -> CloudUploadIntent | None:
    owner_id = _verified_owner(owner)
    try:
        if str(UUID(intent_id)) != intent_id:
            return None
    except (ValueError, TypeError, AttributeError):
        return None

    now = utc_now_naive()
    query = (
        update(CloudUploadIntent)
        .where(
            CloudUploadIntent.id == intent_id,
            CloudUploadIntent.user_id == owner_id,
            CloudUploadIntent.status == expected,
        )
    )
    if expiry_required:
        query = query.where(CloudUploadIntent.expires_at > now)

    values: dict = {"status": target}
    if target == "claimed":
        values["claimed_at"] = now
    elif target == "completed":
        values["completed_at"] = now

    try:
        claimed_id = db.scalar(
            query.values(**values).returning(CloudUploadIntent.id)
        )
        if claimed_id is None:
            db.rollback()
            return None
        db.commit()
        return db.get(CloudUploadIntent, claimed_id)
    except Exception:
        db.rollback()
        raise


def claim_upload_intent(
    *, db: Session, owner: User, intent_id: str,
) -> CloudUploadIntent | None:
    """Single-use compare-and-swap. Missing/expired/replayed IDs fail closed."""
    return _transition(
        db=db, owner=owner, intent_id=intent_id,
        expected="issued", target="claimed", expiry_required=True,
    )


def complete_upload_intent(
    *, db: Session, owner: User, intent_id: str,
) -> CloudUploadIntent | None:
    """Legacy unsafe completion path is intentionally fail-closed.

    A separate status UPDATE cannot atomically create the Document and
    link a final object. Use cloud_document_finalization's verified
    SQL transaction instead. Retain this API as a deliberate no-op so
    old internal callers cannot silently mark an upload as completed.
    """
    _verified_owner(owner)
    return None


def fail_upload_intent(
    *, db: Session, owner: User, intent_id: str,
) -> CloudUploadIntent | None:
    """Fail closed, retain record for audited object garbage collection."""
    return _transition(
        db=db, owner=owner, intent_id=intent_id,
        expected="claimed", target="failed", expiry_required=False,
    )
