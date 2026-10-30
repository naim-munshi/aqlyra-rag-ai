"""Owner-checked cloud document bindings and short-lived private read grants.

Never trust user-supplied cloud:// paths; require an existing completed
owner-bound upload intent linked to this exact Document and checksum.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, settings
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.services.private_object_promotion import assert_owned_final_key
from app.services.private_object_storage import (
    PrivateObjectStorageError, _client, _endpoint,
)

_DOWNLOAD_SECONDS = 45


def verified_cloud_document_key(
    *, db: Session, owner_id: str, document: Document,
    cfg: Settings = settings,
) -> str:
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    if document.user_id != owner_id or not document.storage_path.startswith("cloud://"):
        raise PrivateObjectStorageError("Invalid private document owner or location")
    key = document.storage_path[len("cloud://"):]
    extension = assert_owned_final_key(owner_id=owner_id, key=key)
    if extension != document.file_extension:
        raise PrivateObjectStorageError("Private document extension mismatch")
    record = db.scalar(
        select(CloudUploadIntent)
        .where(
            CloudUploadIntent.user_id == owner_id,
            CloudUploadIntent.document_id == document.id,
            CloudUploadIntent.status == "completed",
            CloudUploadIntent.final_object_key == key,
            CloudUploadIntent.expected_sha256 == document.checksum_sha256,
            CloudUploadIntent.expected_size == document.file_size,
            CloudUploadIntent.content_type == document.content_type,
        )
    )
    if record is None:
        raise PrivateObjectStorageError("Private document binding unavailable")
    return key


def private_document_read_grant(
    *, db: Session, owner_id: str, document: Document,
    cfg: Settings = settings, client=None,
) -> str:
    """45s GET URL after exact user+Document+storage binding verification."""
    key = verified_cloud_document_key(
        db=db, owner_id=owner_id, document=document, cfg=cfg,
    )
    storage = client if client is not None else _client(cfg)
    try:
        url = storage.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": cfg.OBJECT_STORAGE_BUCKET,
                "Key": key,
                "ResponseContentType": document.content_type,
                "ResponseContentDisposition": "attachment",
            },
            ExpiresIn=_DOWNLOAD_SECONDS,
            HttpMethod="GET",
        )
    except Exception as exc:
        raise PrivateObjectStorageError("Cloud download is unavailable") from exc
    if (
        not isinstance(url, str)
        or not url.startswith(_endpoint(cfg.AWS_ENDPOINT_URL_S3) + "/")
    ):
        raise PrivateObjectStorageError("Invalid private download destination")
    return url
