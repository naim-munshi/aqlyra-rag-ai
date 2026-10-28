"""Private, migration-free S3 artifact persistence (explicit opt-in only).

No public ACL, presigned download URL, or cross-account object lookup.
The PostgreSQL advisory transaction lock serializes each owner's quota
across API workers; metadata is written only after artifact bytes exist.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import text

from app.config.settings import settings
from app.database.connection import SessionLocal
from app.services.artifact_rendering import MIMES, render_artifact
from app.services.private_object_storage import (
    _client as neon_private_client,
)

MAX_ARTIFACTS_PER_USER = 50
MAX_METADATA_BYTES = 65536
MAX_RENDERED_BYTES = 25 * 1024 * 1024
_VALID_SHA = re.compile(r"^[0-9a-f]{64}$")


class RemoteArtifactError(Exception):
    """Sanitized storage error; never include provider exception text."""


class RemoteArtifactQuotaError(RemoteArtifactError):
    pass


def _uuid(value: str) -> str:
    try:
        parsed = str(UUID(str(value)))
        if parsed != str(value):
            raise ValueError()
        return parsed
    except (ValueError, AttributeError, TypeError) as exc:
        raise RemoteArtifactError("Invalid artifact identifier") from exc


def _prefix(owner: str) -> str:
    return f"artifacts/{_uuid(owner)}/"


def _key(owner: str, artifact_id: str, extension: str) -> str:
    if extension not in {*MIMES, "json"}:
        raise RemoteArtifactError("Unsupported artifact format")
    return f"{_prefix(owner)}{_uuid(artifact_id)}.{extension}"


def _filename(title: str, fmt: str, artifact_id: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:64]
    return f"{stem or 'aqlyra-artifact'}-{artifact_id[:8]}.{fmt}"


def _storage():
    # This backend must never silently fall back to ephemeral local disk.
    if not (settings.ARTIFACT_REMOTE_STORAGE_ENABLED and settings.PRIVATE_OBJECT_STORAGE_ENABLED):
        raise RemoteArtifactError("Private artifact storage is not enabled")
    try:
        return neon_private_client(settings)
    except Exception as exc:
        raise RemoteArtifactError("Private artifact storage unavailable") from exc


@contextmanager
def _owner_lock(owner: str):
    # Use signed BIGINT advisory transaction lock, cross-process on PostgreSQL.
    lock = int.from_bytes(
        sha256(("aqlyra/artifact/quota/" + _uuid(owner)).encode()).digest()[:8],
        byteorder="big", signed=True,
    )
    try:
        with SessionLocal() as db:
            with db.begin():
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
                yield
    except RemoteArtifactError:
        raise
    except Exception as exc:
        raise RemoteArtifactError("Artifact quota transaction unavailable") from exc


def _list_metadata_keys(s3, owner: str) -> list[str]:
    prefix = _prefix(owner)
    keys: list[str] = []
    continuation = None
    try:
        for _ in range(10):
            args = {"Bucket": settings.OBJECT_STORAGE_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
            if continuation is not None:
                args["ContinuationToken"] = continuation
            page = s3.list_objects_v2(**args)
            for item in page.get("Contents", []):
                key = item.get("Key", "")
                if key.startswith(prefix) and key.endswith(".json"):
                    artifact_id = key[len(prefix):-5]
                    try:
                        if _key(owner, artifact_id, "json") == key:
                            keys.append(key)
                    except RemoteArtifactError:
                        continue
            if len(keys) > MAX_ARTIFACTS_PER_USER + 1000:
                raise RemoteArtifactError("Artifact inventory exceeds safe limit")
            if not page.get("IsTruncated"):
                return keys
            continuation = page.get("NextContinuationToken")
            if not continuation:
                raise RemoteArtifactError("Invalid artifact inventory continuation")
        raise RemoteArtifactError("Artifact inventory pagination limit")
    except RemoteArtifactError:
        raise
    except Exception as exc:
        raise RemoteArtifactError("Private artifact inventory unavailable") from exc


def _read_raw(s3, key: str, *, limit: int) -> bytes | None:
    try:
        result = s3.get_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise RemoteArtifactError("Private artifact read unavailable") from exc
    body = result.get("Body")
    try:
        if body is None or int(result.get("ContentLength", -1)) > limit:
            raise RemoteArtifactError("Artifact exceeds safe size")
        data = body.read(limit + 1)
        if not isinstance(data, bytes) or len(data) > limit:
            raise RemoteArtifactError("Artifact exceeds safe size")
        return data
    except RemoteArtifactError:
        raise
    except Exception as exc:
        # Provider exception messages can contain private endpoints or IDs.
        raise RemoteArtifactError("Private artifact read unavailable") from exc
    finally:
        if body is not None:
            try:
                body.close()
            except Exception:
                pass


def _metadata(s3, owner: str, artifact_id: str) -> dict | None:
    key = _key(owner, artifact_id, "json")
    raw = _read_raw(s3, key, limit=MAX_METADATA_BYTES)
    if raw is None:
        return None
    try:
        item = json.loads(raw)
        if not isinstance(item, dict):
            return None
        fmt = item.get("format")
        title = item.get("title")
        if (item.get("id") != artifact_id or fmt not in MIMES
            or not isinstance(title, str)
            or item.get("filename") != _filename(title, fmt, artifact_id)
            or not isinstance(item.get("content"), str)
            or len(item["content"]) > 24_000
            or not isinstance(item.get("created_at"), str)
            or not isinstance(item.get("source_document_ids"), list)
            or not isinstance(item.get("provider_name"), str)
            or type(item.get("citation_count")) is not int
            or type(item.get("size")) is not int
            or not 0 <= item["size"] <= MAX_RENDERED_BYTES
            or not _VALID_SHA.fullmatch(str(item.get("sha256", "")))):
            return None
        return item
    except (ValueError, TypeError, UnicodeError, AttributeError):
        return None


def create_artifact(*, user_id: str, title: str, kind: str, content: str,
                    provider_name: str, source_document_ids: list[str],
                    citation_count: int) -> dict:
    if kind not in MIMES:
        raise RemoteArtifactError("Unsupported format")
    data = render_artifact(content, kind)
    if len(data) > MAX_RENDERED_BYTES:
        raise RemoteArtifactError("Generated file exceeds safe limit")
    owner = _uuid(user_id)
    artifact_id = str(uuid4())
    item = {
        "id": artifact_id, "title": title[:120], "format": kind,
        "filename": _filename(title[:120], kind, artifact_id),
        "size": len(data), "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_name": provider_name[:80],
        "source_document_ids": source_document_ids,
        "citation_count": citation_count, "content": content,
        "sha256": sha256(data).hexdigest(),
    }
    metadata = json.dumps(item, ensure_ascii=False).encode("utf-8")
    if len(metadata) > MAX_METADATA_BYTES:
        raise RemoteArtifactError("Artifact metadata exceeds safe limit")
    s3 = _storage()
    binary_key = _key(owner, artifact_id, kind)
    meta_key = _key(owner, artifact_id, "json")
    with _owner_lock(owner):
        if len(_list_metadata_keys(s3, owner)) >= MAX_ARTIFACTS_PER_USER:
            raise RemoteArtifactQuotaError("Artifact limit reached. Delete an older file.")
        try:
            s3.put_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=binary_key,
                          Body=data, ContentType=MIMES[kind])
            s3.put_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=meta_key,
                          Body=metadata, ContentType="application/json")
        except Exception as exc:
            # If metadata publishing failed, do not leave a visible item.
            try:
                s3.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=meta_key)
                s3.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=binary_key)
            except Exception:
                pass
            raise RemoteArtifactError("Private artifact write unavailable") from exc
    return {k: v for k, v in item.items() if k != "sha256"}


def read_artifact(*, user_id: str, artifact_id: str) -> dict | None:
    owner = _uuid(user_id)
    try:
        key = _uuid(artifact_id)
    except RemoteArtifactError:
        return None
    item = _metadata(_storage(), owner, key)
    return {k: v for k, v in item.items() if k != "sha256"} if item else None


def list_artifacts(*, user_id: str) -> list[dict]:
    owner = _uuid(user_id)
    s3 = _storage()
    items = []
    for key in _list_metadata_keys(s3, owner):
        artifact_id = key.rsplit("/", 1)[1][:-5]
        meta = _metadata(s3, owner, artifact_id)
        if meta is not None:
            items.append({k: v for k, v in meta.items() if k not in ("content", "sha256")})
    return sorted(items, key=lambda m: m["created_at"], reverse=True)


def artifact_download(*, user_id: str, artifact_id: str) -> tuple[bytes, dict] | None:
    owner = _uuid(user_id)
    try:
        artifact_id = _uuid(artifact_id)
    except RemoteArtifactError:
        return None
    s3 = _storage()
    meta = _metadata(s3, owner, artifact_id)
    if meta is None:
        return None
    binary = _read_raw(s3, _key(owner, artifact_id, meta["format"]), limit=MAX_RENDERED_BYTES)
    if (binary is None or len(binary) != meta["size"]
        or sha256(binary).hexdigest() != meta["sha256"]):
        raise RemoteArtifactError("Private artifact integrity check failed")
    return binary, {k: v for k, v in meta.items() if k != "sha256"}


def delete_artifact(*, user_id: str, artifact_id: str) -> bool:
    owner = _uuid(user_id)
    try:
        artifact_id = _uuid(artifact_id)
    except RemoteArtifactError:
        return False
    s3 = _storage()
    with _owner_lock(owner):
        meta = _metadata(s3, owner, artifact_id)
        if meta is None:
            return False
        try:
            # Remove bytes first, metadata last (metadata is the visibility marker).
            s3.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET,
                             Key=_key(owner, artifact_id, meta["format"]))
            s3.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET,
                             Key=_key(owner, artifact_id, "json"))
        except Exception as exc:
            raise RemoteArtifactError("Private artifact deletion unavailable") from exc
    return True
