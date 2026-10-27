"""Owner-bound, retry-safe deletion of both cloud object copies.

The browser's original stage PUT grant can remain valid briefly after
deletion. Delete stage bytes immediately, and retain a durable tombstone
so the operator sweep deletes any replayed stage copy after grant expiry.
Remote operations precede the DB commit; failure leaves the Document row
for idempotent retry. No arbitrary object keys are accepted.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.services.cloud_document_access import verified_cloud_document_key
from app.services.private_object_storage import (
    PrivateObjectStorageError, _client, assert_owned_key,
)


def delete_cloud_document(*, db: Session, owner_id: str, document_id: str):
    if not settings.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private storage disabled")
    try:
        locked = db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == owner_id,
            ).with_for_update()
        )
        if locked is None:
            return False
        final_key = verified_cloud_document_key(
            db=db, owner_id=owner_id, document=locked,
        )
        intent = db.scalar(
            select(CloudUploadIntent).where(
                CloudUploadIntent.user_id == owner_id,
                CloudUploadIntent.document_id == document_id,
                CloudUploadIntent.final_object_key == final_key,
                CloudUploadIntent.status == "completed",
                CloudUploadIntent.deleted_at.is_(None),
            ).with_for_update()
        )
        if intent is None:
            raise PrivateObjectStorageError("Private document deletion binding unavailable")
        # The staging key comes from owner-verified SQL, never from the client.
        assert_owned_key(owner_id=owner_id, key=intent.object_key)
        store = _client(settings)
        bucket = settings.OBJECT_STORAGE_BUCKET
        if intent.stage_deleted_at is None:
            # Best-effort is NOT sufficient for privacy deletion: if this
            # fails, leave the Document row intact and return a retry error.
            store.delete_object(Bucket=bucket, Key=intent.object_key)
        store.delete_object(Bucket=bucket, Key=final_key)
        # Keep stage_deleted_at unset when a grant may still be writable.
        # The delayed, operator-controlled sweep re-deletes after expiry.
        intent.deleted_at = utc_now_naive()
        db.delete(locked)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PrivateObjectStorageError):
            raise
        raise PrivateObjectStorageError(
            "Private cloud document deletion failed; retry"
        ) from exc
