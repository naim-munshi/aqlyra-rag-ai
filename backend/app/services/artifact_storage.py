"""Owner-scoped artifact storage on the existing persistent upload volume.

No migrations, no executable content, no user-controlled filesystem paths.
Metadata and rendered bytes share a stable per-user directory.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.config.settings import settings
from app.services.artifact_rendering import MIMES, render_artifact

MAX_ARTIFACTS_PER_USER = 50


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


def create_artifact(
    *, user_id: str, title: str, kind: str, content: str,
    provider_name: str, source_document_ids: list[str],
    citation_count: int,
) -> dict:
    if kind not in MIMES:
        raise ArtifactStorageError("Unsupported format")
    folder = _owner_dir(user_id)
    if len(list(folder.glob("*.json"))) >= MAX_ARTIFACTS_PER_USER:
        raise ArtifactQuotaError("Artifact limit reached (50). Delete an older file.")
    data = render_artifact(content, kind)
    artifact_id = str(uuid4())
    filename = _name(title, kind, artifact_id)
    binary_path = folder / f"{artifact_id}.{kind}"
    metadata_path = _record_path(folder, artifact_id)
    metadata = {
        "id": artifact_id,
        "title": title[:120],
        "format": kind,
        "filename": filename,
        "size": len(data),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_name": provider_name[:80],
        "source_document_ids": source_document_ids,
        "citation_count": citation_count,
        "content": content,
    }
    try:
        with binary_path.open("xb") as handle:
            os.chmod(binary_path, 0o600)
            handle.write(data)
            handle.flush()
        with metadata_path.open("x", encoding="utf-8") as handle:
            os.chmod(metadata_path, 0o600)
            json.dump(metadata, handle, ensure_ascii=False)
    except Exception:
        binary_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise
    return metadata


def read_artifact(*, user_id: str, artifact_id: str) -> dict | None:
    folder = _owner_dir(user_id)
    path = _record_path(folder, artifact_id)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            metadata = json.load(handle)
        if metadata.get("id") != _validated_uuid(artifact_id):
            return None
        if metadata.get("format") not in MIMES:
            return None
        return metadata
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def list_artifacts(*, user_id: str) -> list[dict]:
    folder = _owner_dir(user_id)
    results: list[dict] = []
    for path in folder.glob("*.json"):
        item = read_artifact(user_id=user_id, artifact_id=path.stem)
        if item:
            results.append({key: value for key, value in item.items() if key != "content"})
    return sorted(results, key=lambda item: item["created_at"], reverse=True)


def artifact_download(*, user_id: str, artifact_id: str) -> tuple[Path, dict] | None:
    item = read_artifact(user_id=user_id, artifact_id=artifact_id)
    if item is None:
        return None
    folder = _owner_dir(user_id)
    path = folder / f"{_validated_uuid(artifact_id)}.{item['format']}"
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size != item["size"]:
        return None
    return path, item


def delete_artifact(*, user_id: str, artifact_id: str) -> bool:
    item = read_artifact(user_id=user_id, artifact_id=artifact_id)
    if item is None:
        return False
    folder = _owner_dir(user_id)
    path = folder / f"{_validated_uuid(artifact_id)}.{item['format']}"
    if path.is_symlink() or not path.is_file():
        return False
    path.unlink()
    _record_path(folder, artifact_id).unlink(missing_ok=True)
    return True
