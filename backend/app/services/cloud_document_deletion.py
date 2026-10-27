"""Owner-bound, retry-safe remote-first deletion of a cloud Document.

Remote S3 deletion occurs before the metadata transaction commits.
If the remote call fails, metadata stays intact. If SQL commit fails
after a remote delete, metadata remains and a retry can repeat the
idempotent S3 delete. No new orphaned private final objects are created.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.document import Document
from app.services.cloud_document_access import verified_cloud_document_key
from app.services.private_object_storage import (
    PrivateObjectStorageError, _client,
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
        key = verified_cloud_document_key(
            db=db, owner_id=owner_id, document=locked,
        )
        store = _client(settings)
        # S3 delete is idempotent and does not accept an arbitrary client key.
        store.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
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
