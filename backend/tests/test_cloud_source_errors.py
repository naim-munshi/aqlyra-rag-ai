"""Synthetic storage errors must not leak S3 details or mask caller failures."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.cloud_process_io as cloud_io
from app.services.private_object_storage import PrivateObjectStorageError


class Body:
    def __init__(self, value: bytes, *, fails: bool = False):
        self.value = value
        self.fails = fails
        self.closed = False

    def iter_chunks(self, chunk_size):
        if self.fails:
            raise OSError("PRIVATE-S3-STREAM-DETAIL")
        yield self.value

    def close(self):
        self.closed = True


class Storage:
    def __init__(self, data: bytes, *, missing: bool = False, fails: bool = False):
        self.data = data
        self.body = Body(data, fails=fails)
        self.missing = missing

    def get_object(self, *, Bucket, Key):
        assert Key == "owner-verified-key"
        if self.missing:
            raise KeyError("PRIVATE-S3-OBJECT-KEY")
        return {"ContentLength": len(self.data), "Body": self.body}


def _document(data):
    return SimpleNamespace(
        file_size=len(data),
        file_extension=".txt",
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )


def _mock_owner_binding(monkeypatch):
    monkeypatch.setattr(
        cloud_io, "verified_cloud_document_key",
        lambda **kw: "owner-verified-key",
    )
    monkeypatch.setattr(
        cloud_io, "_validate_file_content",
        lambda *args, **kwargs: None,
    )


def test_unavailable_source_is_sanitized_before_caller(monkeypatch):
    _mock_owner_binding(monkeypatch)
    data = b"synthetic source"
    fake = Storage(data, missing=True)
    with pytest.raises(PrivateObjectStorageError) as exc:
        with cloud_io.cloud_processing_source(
            db=object(), owner_id="owner", document=_document(data), store=fake,
        ):
            pytest.fail("Never yield an absent private cloud original")
    assert "PRIVATE-S3" not in str(exc.value)
    assert "could not be verified" in str(exc.value)


def test_stream_error_is_sanitized_and_closed(monkeypatch):
    _mock_owner_binding(monkeypatch)
    data = b"synthetic source"
    fake = Storage(data, fails=True)
    with pytest.raises(PrivateObjectStorageError) as exc:
        with cloud_io.cloud_processing_source(
            db=object(), owner_id="owner", document=_document(data), store=fake,
        ):
            pytest.fail("Should not process an interrupted object")
    assert "PRIVATE-S3-STREAM" not in str(exc.value)
    assert fake.body.closed


def test_successful_verified_source_cleans_up_file(monkeypatch):
    _mock_owner_binding(monkeypatch)
    data = b"synthetic source"
    fake = Storage(data)
    with cloud_io.cloud_processing_source(
        db=object(), owner_id="owner", document=_document(data), store=fake,
    ) as source:
        result = Path(source)
        assert result.read_bytes() == data
        assert result.is_file()
    assert not result.exists()
    assert fake.body.closed


def test_downstream_error_keeps_original_failure_class(monkeypatch):
    _mock_owner_binding(monkeypatch)
    data = b"synthetic source"
    fake = Storage(data)
    with pytest.raises(RuntimeError, match="MODEL_DOWNSTREAM"):
        with cloud_io.cloud_processing_source(
            db=object(), owner_id="owner", document=_document(data), store=fake,
        ):
            raise RuntimeError("MODEL_DOWNSTREAM")
    assert fake.body.closed
