"""Authenticated small private-cloud uploads without cross-origin browser PUT.

This safe initial path is capped below Vercel's function request-size limit.
The uploaded payload only exists in a bounded temporary file, is checked
for content-type and SHA256, then is durably stored in Neon private S3.
An immutable final S3 key and owner-scoped Document record are committed
by the existing single-use cloud finalization service.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.user import User
from app.services.cloud_document_finalization import finalize_cloud_upload
from app.services.cloud_upload_intent_service import reserve_upload_intent
from app.services.document_service import get_user_document
from app.services.private_object_storage import (
    PrivateObjectStorageError, _client,
)
from app.services.storage_service import (
    EmptyFileError,
    FileTooLargeError,
    _get_extension,
    _sanitize_original_filename,
    _validate_file_content,
)

# Vercel 4.5 MB payload cap includes multipart overhead and buffering.
MAX_PROXY_FILE_BYTES = 3 * 1024 * 1024
_CHUNK_BYTES = 256 * 1024


async def persist_small_private_cloud_upload(
    *, upload: UploadFile, db: Session, owner: User,
):
    if not (
        settings.PRIVATE_OBJECT_STORAGE_ENABLED
        and settings.CLOUD_UPLOAD_PROXY_ENABLED
    ):
        raise PrivateObjectStorageError("Private upload is not enabled")

    # Verify the owner before reading any file content or allocating space.
    from app.services.cloud_upload_intent_service import _verified_owner
    owner_id = _verified_owner(owner)
    filename = _sanitize_original_filename(upload.filename)
    extension = _get_extension(filename)

    digest = hashlib.sha256()
    size = 0
    # This is scratch space only. Permanent user objects are NEVER local.
    with tempfile.TemporaryDirectory(prefix="aqlyra-proxy-") as scratch:
        path = Path(scratch) / ("upload" + extension)
        with path.open("xb") as output:
            while True:
                chunk = await upload.read(_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_PROXY_FILE_BYTES:
                    raise FileTooLargeError(
                        "For this launch, use a file of 3 MB or less"
                    )
                output.write(chunk)
                digest.update(chunk)
        if size == 0:
            raise EmptyFileError("The document is empty")
        # Reject malformed PDFs, Office archives and images before any
        # signed grant or cloud DB intent is allocated.
        expected_content_type = _validate_file_content(path, extension)
        storage = _client(settings)
        reserved = reserve_upload_intent(
            db=db,
            owner=owner,
            original_filename=filename,
            expected_size=size,
            expected_sha256=digest.hexdigest(),
            client=storage,
        )
        if reserved.grant.content_type != expected_content_type:
            raise PrivateObjectStorageError("Private upload type mismatch")

        try:
            with path.open("rb") as source:
                storage.put_object(
                    Bucket=settings.OBJECT_STORAGE_BUCKET,
                    Key=reserved.grant.key,
                    Body=source,
                    ContentLength=size,
                    ContentType=reserved.grant.content_type,
                )
        except Exception as exc:
            # Retain the owner-scoped issued intent for operator recovery.
            # Never delete objects by a prefix or mutate existing uploads.
            raise PrivateObjectStorageError(
                "Private document write failed"
            ) from exc

        # Final key is separate from short-lived staging grant, independently
        # checked by SHA256 and committed with the Document row.
        result = finalize_cloud_upload(
            db=db, owner=owner, intent_id=reserved.intent_id,
            client=storage,
        )
        document = get_user_document(
            db=db, user_id=owner_id, document_id=result.document_id,
        )
        if document is None:
            raise PrivateObjectStorageError(
                "Private document is not yet available"
            )
        return document
