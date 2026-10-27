"""Private Neon S3-compatible storage primitives, deliberately not wired to uploads.

Existing local documents remain authoritative until authenticated finalize,
DB consistency, processing and cleanup are accepted end-to-end. No public
bucket access or direct upload URLs for unverified clients are exposed here.
"""
from __future__ import annotations

import hashlib
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import boto3
from botocore.config import Config

from app.config.settings import Settings, settings
from app.services.storage_service import (
    _get_extension,
    _sanitize_original_filename,
    _validate_file_content,
)

_CONTENT_TYPE = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SECONDS = 120


class PrivateObjectStorageError(Exception):
    """Sanitized storage-layer failure; never echo signed URLs or credentials."""


@dataclass(frozen=True)
class UploadGrant:
    key: str
    put_url: str
    content_type: str
    headers: dict[str, str]
    expires_in_seconds: int


def _uuid(value: str) -> str:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise PrivateObjectStorageError("Invalid user or object ID") from exc
    if str(parsed) != value:
        raise PrivateObjectStorageError("Invalid user or object ID")
    return value


def object_key(*, owner_id: str, object_id: str, extension: str) -> str:
    """Keys are generated from immutable UUIDs, not attacker-supplied paths."""
    owner = _uuid(owner_id)
    object_key_id = _uuid(object_id)
    if extension not in _CONTENT_TYPE:
        raise PrivateObjectStorageError("Unsupported extension")
    return f"documents/{owner}/{object_key_id}{extension}"


def assert_owned_key(*, owner_id: str, key: str) -> str:
    owner = _uuid(owner_id)
    match = re.fullmatch(
        r"documents/([0-9a-f-]{36})/([0-9a-f-]{36})(\.[a-z0-9]+)",
        key,
    )
    if not match or match.group(1) != owner:
        raise PrivateObjectStorageError("Object is not owned by this account")
    expected = object_key(
        owner_id=match.group(1), object_id=match.group(2),
        extension=match.group(3),
    )
    if expected != key:
        raise PrivateObjectStorageError("Invalid object key")
    return match.group(3)


def _endpoint(value: str) -> str:
    """Allow only HTTPS Neon object endpoints; never arbitrary SSRF targets."""
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https" or not hostname.endswith(".aws.neon.tech")
        or parsed.username or parsed.password or parsed.port
        or parsed.query or parsed.fragment or parsed.path not in ("", "/")
    ):
        raise PrivateObjectStorageError("Invalid private Neon storage endpoint")
    return f"https://{hostname}"


def _client(cfg: Settings):
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    try:
        endpoint = _endpoint(cfg.AWS_ENDPOINT_URL_S3)
        if not all([
            cfg.AWS_ACCESS_KEY_ID, cfg.AWS_SECRET_ACCESS_KEY,
            cfg.AWS_REGION, cfg.OBJECT_STORAGE_BUCKET,
        ]):
            raise PrivateObjectStorageError("Private storage is not configured")
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=cfg.AWS_REGION,
            aws_access_key_id=cfg.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=cfg.AWS_SECRET_ACCESS_KEY,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=15,
                retries={"max_attempts": 1},
            ),
        )
    except PrivateObjectStorageError:
        raise
    except Exception as exc:
        raise PrivateObjectStorageError("Private object storage unavailable") from exc


def prepare_private_upload(
    *, owner_id: str, filename: str, size_bytes: int,
    cfg: Settings = settings, client=None,
) -> UploadGrant:
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise PrivateObjectStorageError("Private object storage is disabled")
    if not 0 < size_bytes <= cfg.max_upload_size_bytes:
        raise PrivateObjectStorageError("Invalid upload size")
    name = _sanitize_original_filename(filename)
    extension = _get_extension(name)
    owner_id = _uuid(owner_id)
    key = object_key(
        owner_id=owner_id, object_id=str(uuid4()), extension=extension,
    )
    content_type = _CONTENT_TYPE[extension]
    storage = client if client is not None else _client(cfg)
    try:
        url = storage.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": cfg.OBJECT_STORAGE_BUCKET,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=_SECONDS,
            HttpMethod="PUT",
        )
    except Exception as exc:
        raise PrivateObjectStorageError("Unable to prepare private upload") from exc
    if not isinstance(url, str) or not url.startswith(
        _endpoint(cfg.AWS_ENDPOINT_URL_S3) + "/"
    ):
        raise PrivateObjectStorageError("Unexpected storage upload destination")
    return UploadGrant(
        key=key, put_url=url, content_type=content_type,
        headers={"Content-Type": content_type},
        expires_in_seconds=_SECONDS,
    )


@contextmanager
def verified_private_temporary_file(
    *, owner_id: str, key: str, expected_size: int, expected_sha256: str,
    cfg: Settings = settings, client=None,
) -> Iterator[Path]:
    """Stream 25 MB max to temporary storage, then validate magic/content.

    The caller must first verify account ownership and persist a signed
    upload-intent/expiry in a transactional store; this primitive does not
    establish that protocol and must not be used as a public finalize route.
    """
    extension = assert_owned_key(owner_id=owner_id, key=key)
    if (
        not cfg.PRIVATE_OBJECT_STORAGE_ENABLED
        or not 0 < expected_size <= cfg.max_upload_size_bytes
        or not _HASH.fullmatch(expected_sha256)
    ):
        raise PrivateObjectStorageError("Invalid private upload metadata")
    storage = client if client is not None else _client(cfg)
    tmp = None
    try:
        result = storage.get_object(Bucket=cfg.OBJECT_STORAGE_BUCKET, Key=key)
        if int(result["ContentLength"]) != expected_size:
            raise PrivateObjectStorageError("Stored object size mismatch")
        tmp = tempfile.NamedTemporaryFile(
            prefix="aqlyra-verified-", suffix=extension, delete=False,
        )
        temporary_path = Path(tmp.name)
        checksum = hashlib.sha256()
        total = 0
        with tmp:
            body = result["Body"]
            try:
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > expected_size:
                        raise PrivateObjectStorageError("Stored object exceeds size limit")
                    checksum.update(chunk)
                    tmp.write(chunk)
            finally:
                close = getattr(body, "close", None)
                if callable(close):
                    close()
        if total != expected_size or checksum.hexdigest() != expected_sha256:
            raise PrivateObjectStorageError("Stored object checksum mismatch")
        _validate_file_content(temporary_path, extension)
    except PrivateObjectStorageError:
        raise
    except Exception as exc:
        raise PrivateObjectStorageError("Private object could not be verified") from exc
    else:
        # Caller exceptions must propagate unchanged; this file is still cleaned.
        yield temporary_path
    finally:
        if tmp is not None:
            Path(tmp.name).unlink(missing_ok=True)
