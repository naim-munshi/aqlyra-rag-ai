"""Owner-scoped artifact storage.

Development may use the existing local volume. Production prefers the existing
private Neon S3-compatible bucket; it never falls back to an ephemeral disk when
private storage is enabled but unavailable.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.config.settings import settings
from app.services.storage_durability_policy import (
    artifact_writes_permitted,
    private_object_storage_configured,
    private_object_storage_selected,
)
from app.services.artifact_rendering import MIMES, render_artifact
from app.services.private_object_storage import _client as _private_s3_client

MAX_ARTIFACTS_PER_USER = 50
_MAX_METADATA_BYTES = 128 * 1024
_CHUNK_BYTES = 1024 * 1024
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ArtifactStorageError(Exception):
    pass


class ArtifactQuotaError(ArtifactStorageError):
    pass


def _validated_uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ArtifactStorageError("Invalid identifier") from exc


def _owner_dir(user_id: str) -> Path:
    user_key = _validated_uuid(user_id)
    root = (settings.UPLOAD_DIR.expanduser().resolve() / "artifact-workspace")
    folder = root / user_key
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink() or not folder.resolve().is_relative_to(root.resolve()):
        raise ArtifactStorageError("Unsafe artifact storage path")
    return folder


def _name(title: str, kind: str, key: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:64]
    return f"{stem or 'aqlyra-artifact'}-{key[:8]}.{kind}"


def _record_path(folder: Path, artifact_id: str) -> Path:
    return folder / (_validated_uuid(artifact_id) + ".json")


def _artifact_prefix(user_id: str) -> str:
    return f"artifacts/{_validated_uuid(user_id)}/"


def _artifact_keys(user_id: str, artifact_id: str, kind: str) -> tuple[str, str]:
    owner = _validated_uuid(user_id)
    identity = _validated_uuid(artifact_id)
    if kind not in MIMES:
        raise ArtifactStorageError("Unsupported format")
    prefix = f"artifacts/{owner}/{identity}"
    return f"{prefix}.{kind}", f"{prefix}.json"


def _s3_client():
    if not private_object_storage_configured():
        raise ArtifactStorageError("Private artifact storage is not configured")
    try:
        return _private_s3_client(settings)
    except Exception as exc:
        raise ArtifactStorageError("Private artifact storage unavailable") from exc


def _is_missing_object(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    if not isinstance(response, dict):
        return False
    error = response.get("Error", {})
    metadata = response.get("ResponseMetadata", {})
    code = error.get("Code") if isinstance(error, dict) else None
    status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
    return code in {"404", "NoSuchKey", "NotFound"} or status == 404


def _read_remote_metadata(client, *, user_id: str, artifact_id: str) -> dict | None:
    identity = _validated_uuid(artifact_id)
    key = f"{_artifact_prefix(user_id)}{identity}.json"
    response_body = None
    try:
        result = client.get_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
        response_body = result["Body"]
        raw = response_body.read(_MAX_METADATA_BYTES + 1)
        if len(raw) > _MAX_METADATA_BYTES:
            raise ArtifactStorageError("Artifact metadata exceeds the safety limit")
        item = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        if _is_missing_object(exc):
            return None
        if isinstance(exc, ArtifactStorageError):
            raise
        raise ArtifactStorageError("Artifact metadata unavailable") from exc
    finally:
        if response_body is not None:
            close = getattr(response_body, "close", None)
            if callable(close):
                response_body.close()

    if (
        not isinstance(item, dict)
        or item.get("id") != identity
        or item.get("owner_id") != _validated_uuid(user_id)
        or item.get("format") not in MIMES
        or not isinstance(item.get("size"), int)
        or item["size"] < 0
        or not isinstance(item.get("sha256"), str)
        or not _DIGEST.fullmatch(item["sha256"])
    ):
        raise ArtifactStorageError("Artifact metadata is invalid")
    return item


def _remote_artifact_count(client, user_id: str) -> int:
    try:
        result = client.list_objects_v2(
            Bucket=settings.OBJECT_STORAGE_BUCKET,
            Prefix=_artifact_prefix(user_id),
            MaxKeys=(MAX_ARTIFACTS_PER_USER * 2) + 1,
        )
        objects = result.get("Contents", [])
        if result.get("IsTruncated"):
            raise ArtifactStorageError("Private artifact quota listing was truncated")
        return sum(
            1 for item in objects
            if isinstance(item, dict)
            and str(item.get("Key", "")).endswith(".json")
        )
    except Exception as exc:
        raise ArtifactStorageError("Private artifact quota check unavailable") from exc


def _create_remote_artifact(*, client, metadata: dict, data: bytes, user_id: str) -> None:
    binary_key, metadata_key = _artifact_keys(
        user_id, metadata["id"], metadata["format"],
    )
    metadata_bytes = json.dumps(
        metadata, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    binary_written = False
    try:
        client.put_object(
            Bucket=settings.OBJECT_STORAGE_BUCKET,
            Key=binary_key,
            Body=data,
            ContentType=MIMES[metadata["format"]],
            CacheControl="private, no-store",
        )
        binary_written = True
        client.put_object(
            Bucket=settings.OBJECT_STORAGE_BUCKET,
            Key=metadata_key,
            Body=metadata_bytes,
            ContentType="application/json",
            CacheControl="private, no-store",
        )
    except Exception as exc:
        # Clean up both keys, including ambiguous metadata PUT failures.
        for key in (metadata_key, binary_key):
            try:
                client.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
            except Exception:
                pass
        raise ArtifactStorageError("Private artifact write failed") from exc


@contextmanager
def _artifact_lock(folder: Path):
    """Cross-process quota guard on a shared local persistent volume."""
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(folder / ".quota.lock", flags, 0o600)
    try:
        with os.fdopen(descriptor, "rb+") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
    except BaseException:
        raise


def create_artifact(
    *, user_id: str, title: str, kind: str, content: str,
    provider_name: str, source_document_ids: list[str],
    citation_count: int,
) -> dict:
    if not artifact_writes_permitted():
        raise ArtifactStorageError("Durable artifact storage is not configured")
    owner_id = _validated_uuid(user_id)
    if kind not in MIMES:
        raise ArtifactStorageError("Unsupported format")
    data = render_artifact(content, kind)
    artifact_id = str(uuid4())
    filename = _name(title, kind, artifact_id)
    metadata = {
        "id": artifact_id,
        "owner_id": owner_id,
        "storage_backend": (
            "private_object_storage" if private_object_storage_configured()
            else "local"
        ),
        "title": title[:120],
        "format": kind,
        "filename": filename,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_name": provider_name[:80],
        "source_document_ids": source_document_ids,
        "citation_count": citation_count,
        "content": content,
    }

    # When enabled, private object storage is authoritative. Provider failures
    # fail closed; never silently write to the ephemeral Render filesystem.
    if private_object_storage_configured():
        client = _s3_client()
        if _remote_artifact_count(client, owner_id) >= MAX_ARTIFACTS_PER_USER:
            raise ArtifactQuotaError("Artifact limit reached. Delete an older file.")
        _create_remote_artifact(client=client, metadata=metadata, data=data, user_id=owner_id)
        return metadata

    folder = _owner_dir(owner_id)
    binary_path = folder / f"{artifact_id}.{kind}"
    metadata_path = _record_path(folder, artifact_id)
    with _artifact_lock(folder):
        if len(list(folder.glob("*.json"))) >= MAX_ARTIFACTS_PER_USER:
            raise ArtifactQuotaError("Artifact limit reached. Delete an older file.")
        try:
            with binary_path.open("xb") as handle:
                os.chmod(binary_path, 0o600)
                handle.write(data)
                handle.flush()
            with metadata_path.open("x", encoding="utf-8") as handle:
                os.chmod(metadata_path, 0o600)
                json.dump(metadata, handle, ensure_ascii=False)
                handle.flush()
        except Exception:
            binary_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise
    return metadata


def read_artifact(*, user_id: str, artifact_id: str) -> dict | None:
    owner_id = _validated_uuid(user_id)
    identity = _validated_uuid(artifact_id)
    if private_object_storage_configured():
        item = _read_remote_metadata(
            _s3_client(), user_id=owner_id, artifact_id=identity,
        )
        if item is not None:
            return item
        # Backwards compatibility: artifacts created before private S3 support
        # remain readable from the existing owner-scoped local directory.
    folder = _owner_dir(owner_id)
    path = _record_path(folder, identity)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            metadata = json.load(handle)
        if metadata.get("id") != identity:
            return None
        if metadata.get("format") not in MIMES:
            return None
        return metadata
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def list_artifacts(*, user_id: str) -> list[dict]:
    owner_id = _validated_uuid(user_id)
    results: list[dict] = []
    if private_object_storage_configured():
        client = _s3_client()
        try:
            response = client.list_objects_v2(
                Bucket=settings.OBJECT_STORAGE_BUCKET,
                Prefix=_artifact_prefix(owner_id),
                # 50 artifacts have up to 100 objects (binary + metadata).
                MaxKeys=(MAX_ARTIFACTS_PER_USER * 2) + 1,
            )
            if response.get("IsTruncated"):
                raise ArtifactStorageError("Private artifact listing was truncated")
            keys = [
                str(item.get("Key", ""))
                for item in response.get("Contents", [])
                if isinstance(item, dict) and str(item.get("Key", "")).endswith(".json")
            ]
        except ArtifactStorageError:
            raise
        except Exception as exc:
            raise ArtifactStorageError("Private artifact listing unavailable") from exc
        for key in keys:
            artifact_id = Path(key).stem
            item = _read_remote_metadata(
                client, user_id=owner_id, artifact_id=artifact_id,
            )
            if item:
                results.append({
                    name: value for name, value in item.items()
                    if name not in {"content", "owner_id", "storage_backend"}
                })

    # Merge any legacy/local records that pre-date private object storage.
    folder = _owner_dir(owner_id)
    for path in folder.glob("*.json"):
        item = read_artifact(user_id=owner_id, artifact_id=path.stem)
        if item:
            results.append({key: value for key, value in item.items() if key != "content"})
    # Avoid duplicate IDs if the same record was migrated by an operator.
    unique = {item["id"]: item for item in results}
    return sorted(unique.values(), key=lambda item: item["created_at"], reverse=True)


def _download_temp_root() -> Path:
    root = Path(tempfile.gettempdir()) / "aqlyra-artifact-downloads"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise ArtifactStorageError("Unsafe artifact download path")
    os.chmod(root, 0o700)
    return root


def cleanup_artifact_download(path: str | Path) -> None:
    """Remove only temporary downloads created by this service."""
    try:
        target = Path(path)
        root = _download_temp_root().resolve()
        if target.parent.resolve() == root and target.name.startswith("aqlyra-"):
            if target.is_file() and not target.is_symlink():
                target.unlink(missing_ok=True)
    except OSError:
        # Download cleanup is best-effort; never mask the HTTP response.
        return


def artifact_download(*, user_id: str, artifact_id: str) -> tuple[Path, dict] | None:
    item = read_artifact(user_id=user_id, artifact_id=artifact_id)
    if item is None:
        return None
    identity = _validated_uuid(artifact_id)
    if item.get("storage_backend") == "private_object_storage":
        if not private_object_storage_selected(settings):
            raise ArtifactStorageError("Private artifact storage is disabled")
        binary_key, _ = _artifact_keys(user_id, identity, item["format"])
        client = _s3_client()
        response_body = None
        temporary_path = None
        digest = hashlib.sha256()
        total = 0
        try:
            result = client.get_object(
                Bucket=settings.OBJECT_STORAGE_BUCKET, Key=binary_key,
            )
            response_body = result["Body"]
            if int(result.get("ContentLength", -1)) != item["size"]:
                raise ArtifactStorageError("Artifact object size mismatch")
            with tempfile.NamedTemporaryFile(
                prefix="aqlyra-", suffix=f".{item['format']}",
                dir=_download_temp_root(), delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                os.chmod(temporary_path, 0o600)
                while True:
                    chunk = response_body.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > item["size"]:
                        raise ArtifactStorageError("Artifact object exceeds expected size")
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
            if total != item["size"] or digest.hexdigest() != item["sha256"]:
                raise ArtifactStorageError("Artifact object checksum mismatch")
            return temporary_path, item
        except ArtifactStorageError:
            if temporary_path is not None:
                cleanup_artifact_download(temporary_path)
            raise
        except Exception as exc:
            if temporary_path is not None:
                cleanup_artifact_download(temporary_path)
            if _is_missing_object(exc):
                return None
            raise ArtifactStorageError("Private artifact download unavailable") from exc
        finally:
            if response_body is not None:
                close = getattr(response_body, "close", None)
                if callable(close):
                    response_body.close()

    folder = _owner_dir(user_id)
    path = folder / f"{identity}.{item['format']}"
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size != item["size"]:
        return None
    return path, item


def delete_artifact(*, user_id: str, artifact_id: str) -> bool:
    owner_id = _validated_uuid(user_id)
    identity = _validated_uuid(artifact_id)
    item = read_artifact(user_id=owner_id, artifact_id=identity)
    if item is None:
        return False
    if item.get("storage_backend") == "private_object_storage":
        if not private_object_storage_selected(settings):
            raise ArtifactStorageError("Private artifact storage is disabled")
        client = _s3_client()
        binary_key, metadata_key = _artifact_keys(owner_id, identity, item["format"])
        try:
            client.delete_object(
                Bucket=settings.OBJECT_STORAGE_BUCKET, Key=binary_key,
            )
            client.delete_object(
                Bucket=settings.OBJECT_STORAGE_BUCKET, Key=metadata_key,
            )
        except Exception as exc:
            raise ArtifactStorageError("Private artifact deletion failed") from exc
        return True

    folder = _owner_dir(owner_id)
    with _artifact_lock(folder):
        item = read_artifact(user_id=owner_id, artifact_id=identity)
        if item is None:
            return False
        path = folder / f"{identity}.{item['format']}"
        if path.is_symlink() or not path.is_file():
            return False
        path.unlink()
        _record_path(folder, identity).unlink(missing_ok=True)
        return True
