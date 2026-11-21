"""No external credentials or cloud I/O: security contract for offsite backup."""
import hashlib
import importlib.util
import io
from pathlib import Path
from uuid import uuid4

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "offsite_neon_export.py"
_spec = importlib.util.spec_from_file_location("aqlyra_offsite_export", _SCRIPT)
assert _spec and _spec.loader
backup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup)


def test_backup_prefix_is_unique_even_when_started_same_second():
    stamp = "20261111T130000Z"
    first = backup._unique_backup_prefix(stamp)
    second = backup._unique_backup_prefix(stamp)
    assert first != second
    assert first.startswith("aqlyra/backup-v1/" + stamp + "-")
    assert second.startswith("aqlyra/backup-v1/" + stamp + "-")
    with pytest.raises(backup.BackupRefused):
        backup._unique_backup_prefix("../unsafe")


def test_pg18_export_image_must_be_an_immutable_reviewed_digest(monkeypatch):
    monkeypatch.delenv("AQ_PG18_IMAGE", raising=False)
    with pytest.raises(backup.BackupRefused):
        backup._pinned_pg18_image()
    monkeypatch.setenv("AQ_PG18_IMAGE", "postgres:18")
    with pytest.raises(backup.BackupRefused):
        backup._pinned_pg18_image()
    pinned = "postgres:18@sha256:" + ("a" * 64)
    monkeypatch.setenv("AQ_PG18_IMAGE", pinned)
    assert backup._pinned_pg18_image() == pinned


def test_offsite_backup_fails_closed_without_confirmed_environment(monkeypatch):
    monkeypatch.delenv("AQ_OFFSITE_BACKUP_ENABLED", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(backup.BackupRefused):
        backup._preflight()


def test_backup_refuses_same_source_and_destination(monkeypatch):
    values = {
        "GITHUB_ACTIONS": "true",
        "AQ_OFFSITE_BACKUP_ENABLED": "yes",
        "AQ_OFFSITE_BACKUP_CONFIRMED": "offsite-v1",
        "AQ_AGE_PUBLIC_RECIPIENT": "age1" + "q" * 60,
        "AQ_OFFSITE_BUCKET": "same-backup-bucket",
        "AQ_SOURCE_BUCKET": "same-backup-bucket",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(backup.BackupRefused):
        backup._preflight()


def test_completed_owner_objects_have_safe_nonplaintext_archive_paths():
    owner = str(uuid4())
    key = f"final/documents/{owner}/{uuid4()}.pdf"
    sha = hashlib.sha256(b"safe synthetic").hexdigest()
    archive = backup._key_and_label(key=key, owner=owner, expected_sha=sha, size=14)
    assert archive.startswith("objects/")
    assert archive.endswith(".bin")
    assert owner not in archive
    assert key not in archive


@pytest.mark.parametrize("bad", [
    "final/documents/other-owner/example.pdf",
    "final/documents/../../private.pdf",
    "../secrets",
    "/absolute/file.pdf",
    "staging/key.pdf",
])
def test_untrusted_key_never_becomes_tar_path(bad):
    with pytest.raises(backup.BackupRefused):
        backup._key_and_label(
            key=bad, owner=str(uuid4()),
            expected_sha=hashlib.sha256(b"ok").hexdigest(), size=2,
        )


def test_object_reader_validates_streaming_sha_and_truncation():
    content = b"public-only" * 10
    reader = backup._VerifyingObjectReader(io.BytesIO(content), len(content))
    result = bytearray()
    while True:
        part = reader.read(13)
        if not part:
            break
        result.extend(part)
    assert bytes(result) == content
    reader.verify(hashlib.sha256(content).hexdigest())

    corrupt = backup._VerifyingObjectReader(io.BytesIO(b"wrong"), len(content))
    with pytest.raises(backup.BackupRefused):
        while_part = corrupt.read(len(content))
        corrupt.read(len(content))


def test_object_reader_rejects_checksum_drift():
    data = b"public-only"
    reader = backup._VerifyingObjectReader(io.BytesIO(data), len(data))
    assert reader.read() == data
    with pytest.raises(backup.BackupRefused):
        reader.verify(hashlib.sha256(b"other").hexdigest())
