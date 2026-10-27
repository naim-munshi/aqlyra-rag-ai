"""Internal verified promotion from browser-writable staging to private final object.

No API routes call this service yet. Promotion alone does not create a
Document row or complete an upload intent; the durable orchestration,
recovery and reconciliation gate is intentionally pending.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import uuid4

from app.config.settings import Settings, settings
from app.services.private_object_storage import (
    PrivateObjectStorageError,
    _CONTENT_TYPE,
    _HASH,
    _client,
    _uuid,
    assert_owned_key,
    verified_private_temporary_file,
)


@dataclass(frozen=True)
class PromotedPrivateObject:
    """Server-writable only; no browser presigned PUT is created for this key."""

    key: str
    size_bytes: int
    sha256: str
    content_type: str


def final_object_key(*, owner_id: str, object_id: str, extension: str) -> str:
    """Unpredictable final key under a separate prefix from upload staging."""
    owner = _uuid(owner_id)
    identifier = _uuid(object_id)
    if extension not in _CONTENT_TYPE:
        raise PrivateObjectStorageError("Unsupported final object type")
    return f"final/documents/{owner}/{identifier}{extension}"


def assert_owned_final_key(*, owner_id: str, key: str) -> str:
    owner = _uuid(owner_id)
    match = re.fullmatch(
        r"final/documents/([0-9a-f-]{36})/([0-9a-f-]{36})(\.[a-z0-9]+)",
        key,
    )
    if not match or match.group(1) != owner:
        raise PrivateObjectStorageError("Final object is not owned by this account")
    if final_object_key(
        owner_id=match.group(1),
        object_id=match.group(2),
        extension=match.group(3),
    ) != key:
        raise PrivateObjectStorageError("Invalid final object key")
    return match.group(3)


def _verify_final_bytes(
    *, storage, bucket: str, key: str, expected_size: int, expected_sha256: str,
) -> None:
    """Never rely on the S3 ETag as a SHA-256 integrity certificate."""
    response = storage.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        if int(response["ContentLength"]) != expected_size:
            raise PrivateObjectStorageError("Promoted object size mismatch")

        checksum = hashlib.sha256()
        read_size = 0
        for chunk in body.iter_chunks(chunk_size=1_048_576):
            if not chunk:
                continue
            read_size += len(chunk)
            if read_size > expected_size:
                raise PrivateObjectStorageError("Promoted object exceeds size limit")
            checksum.update(chunk)
        if read_size != expected_size or checksum.hexdigest() != expected_sha256:
            raise PrivateObjectStorageError("Promoted object checksum mismatch")
    finally:
        close = getattr(body, "close", None)
        if close is not None:
            close()


def promote_verified_private_upload(
    *,
    owner_id: str,
    staging_key: str,
    expected_size: int,
    expected_sha256: str,
    cfg: Settings = settings,
    client=None,
    final_key: str | None = None,
) -> PromotedPrivateObject:
    """Verify staging bytes, upload a distinct final key, then verify again.

    This is an *internal primitive*, not a transactional finalizer.
    The caller must ensure it holds a single-use claimed intent and
    must persist a durable record or arrange orphan reconciliation.
    Browser grants apply only to the staging prefix, never final keys.

    On in-process failure after final upload, best-effort deletion runs.
    Crashes between remote upload and DB commit require later GC.
    """
    extension = assert_owned_key(owner_id=owner_id, key=staging_key)
    if (
        not cfg.PRIVATE_OBJECT_STORAGE_ENABLED
        or not 0 < expected_size <= cfg.max_upload_size_bytes
        or _HASH.fullmatch(expected_sha256) is None
    ):
        raise PrivateObjectStorageError("Invalid private upload metadata")
    storage = client if client is not None else _client(cfg)
    if final_key is None:
        final_key = final_object_key(
            owner_id=owner_id, object_id=str(uuid4()), extension=extension,
        )
    elif assert_owned_final_key(owner_id=owner_id, key=final_key) != extension:
        raise PrivateObjectStorageError("Final object type does not match staging")
    bucket = cfg.OBJECT_STORAGE_BUCKET
    with verified_private_temporary_file(
        owner_id=owner_id,
        key=staging_key,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
        cfg=cfg,
        client=storage,
    ) as verified:
        try:
            with verified.open("rb") as source:
                storage.put_object(
                    Bucket=bucket,
                    Key=final_key,
                    Body=source,
                    ContentLength=expected_size,
                    ContentType=_CONTENT_TYPE[extension],
                )
            _verify_final_bytes(
                storage=storage,
                bucket=bucket,
                key=final_key,
                expected_size=expected_size,
                expected_sha256=expected_sha256,
            )
        except Exception as exc:
            try:
                storage.delete_object(Bucket=bucket, Key=final_key)
            except Exception:
                # A durable orphan sweeper is a release requirement.
                # Never leak provider exception details to clients.
                pass
            if isinstance(exc, PrivateObjectStorageError):
                raise
            raise PrivateObjectStorageError(
                "Private object promotion or verification failed"
            ) from exc

    return PromotedPrivateObject(
        key=final_key,
        size_bytes=expected_size,
        sha256=expected_sha256,
        content_type=_CONTENT_TYPE[extension],
    )


def discard_promoted_private_object(
    *, owner_id: str, final_key: str,
    cfg: Settings = settings, client=None,
) -> None:
    """Owner-isolated compensating action, for a *failed* DB finalization.

    The caller must first confirm no committed Document references the key.
    Never expose this primitive as a user-controlled delete endpoint.
    """
    assert_owned_final_key(owner_id=owner_id, key=final_key)
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    storage = client if client is not None else _client(cfg)
    try:
        storage.delete_object(Bucket=cfg.OBJECT_STORAGE_BUCKET, Key=final_key)
    except Exception as exc:
        raise PrivateObjectStorageError(
            "Unable to remove failed private object"
        ) from exc


def verify_existing_final_private_object(
    *,
    owner_id: str, final_key: str,
    expected_size: int, expected_sha256: str,
    cfg: Settings = settings, client=None,
) -> PromotedPrivateObject:
    """Idempotent recovery: rehash committed remote bytes before DB linkage.

    Must only be called after checking an owner-bound claimed intent whose
    final_object_key was persisted BEFORE the remote upload. This function
    has no delete or mutating side effects.
    """
    extension = assert_owned_final_key(owner_id=owner_id, key=final_key)
    if (
        not cfg.PRIVATE_OBJECT_STORAGE_ENABLED
        or not 0 < expected_size <= cfg.max_upload_size_bytes
        or _HASH.fullmatch(expected_sha256) is None
    ):
        raise PrivateObjectStorageError("Invalid private final object metadata")
    storage = client if client is not None else _client(cfg)
    try:
        _verify_final_bytes(
            storage=storage, bucket=cfg.OBJECT_STORAGE_BUCKET, key=final_key,
            expected_size=expected_size, expected_sha256=expected_sha256,
        )
    except PrivateObjectStorageError:
        raise
    except Exception as exc:
        raise PrivateObjectStorageError(
            "Private final object could not be verified"
        ) from exc
    return PromotedPrivateObject(
        key=final_key, size_bytes=expected_size,
        sha256=expected_sha256, content_type=_CONTENT_TYPE[extension],
    )
