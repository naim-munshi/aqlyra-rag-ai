"""Neon private S3 upload primitives: signed URL, owner isolation and checksum."""
import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.services.private_object_storage import (
    PrivateObjectStorageError,
    _client,
    assert_owned_key,
    object_key,
    prepare_private_upload,
    verified_private_temporary_file,
)


_ENDPOINT = "https://br-private-example.storage.c-2.us-east-2.aws.neon.tech"


def configured(**overrides):
    defaults = {
        "PRIVATE_OBJECT_STORAGE_ENABLED": True,
        "AWS_ENDPOINT_URL_S3": _ENDPOINT,
        "AWS_REGION": "us-east-2",
        "AWS_ACCESS_KEY_ID": "private-test-access-id",
        "AWS_SECRET_ACCESS_KEY": "private-test-secret-should-stay-private",
        "OBJECT_STORAGE_BUCKET": "private-documents",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


class FakeS3:
    def __init__(self, data=b"hello uploaded file"):
        self.data = data
        self.signed = []
        self.reads = []

    def generate_presigned_url(self, method, **kwargs):
        self.signed.append((method, kwargs))
        return (
            f"{_ENDPOINT}/{kwargs['Params']['Bucket']}/"
            f"{kwargs['Params']['Key']}?X-Amz-Signature=synthetic"
        )

    def get_object(self, **kwargs):
        self.reads.append(kwargs)
        data = self.data

        class Body:
            def iter_chunks(self, chunk_size):
                for start in range(0, len(data), chunk_size):
                    yield data[start:start + chunk_size]

        return {"ContentLength": len(data), "Body": Body()}


def test_feature_is_disabled_by_default():
    settings = Settings(_env_file=None)
    assert settings.PRIVATE_OBJECT_STORAGE_ENABLED is False
    with pytest.raises(PrivateObjectStorageError, match="disabled"):
        prepare_private_upload(
            owner_id=str(uuid4()), filename="a.txt", size_bytes=1, cfg=settings,
            client=FakeS3(),
        )


def test_signed_upload_grant_uses_isolated_random_key():
    client = FakeS3()
    owner = str(uuid4())
    config = configured()
    first = prepare_private_upload(
        owner_id=owner, filename="safe.txt", size_bytes=25,
        cfg=config, client=client,
    )
    second = prepare_private_upload(
        owner_id=owner, filename="safe.txt", size_bytes=25,
        cfg=config, client=client,
    )
    assert first.key != second.key
    assert first.key.startswith("documents/" + owner + "/")
    assert first.key.endswith(".txt")
    assert first.expires_in_seconds == 600
    assert first.headers == {"Content-Type": "text/plain"}
    assert "X-Amz-Signature=" in first.put_url
    method, kwargs = client.signed[0]
    assert method == "put_object"
    assert kwargs["HttpMethod"] == "PUT"
    assert kwargs["ExpiresIn"] == 600
    assert kwargs["Params"] == {
        "Bucket": "private-documents",
        "Key": first.key,
        "ContentType": "text/plain",
    }


@pytest.mark.parametrize("filename,size", [
    ("bad.exe", 10), ("a.txt", 0), ("a.txt", -1),
    ("a.txt", 25 * 1024 * 1024 + 1),
])
def test_rejects_invalid_upload(filename, size):
    client = FakeS3()
    with pytest.raises(Exception):
        prepare_private_upload(
            owner_id=str(uuid4()), filename=filename,
            size_bytes=size, cfg=configured(), client=client,
        )
    assert client.signed == []


def test_bad_user_or_cross_tenant_key_is_rejected():
    owner = str(uuid4())
    key = object_key(owner_id=owner, object_id=str(uuid4()), extension=".pdf")
    assert assert_owned_key(owner_id=owner, key=key) == ".pdf"
    with pytest.raises(PrivateObjectStorageError, match="not owned"):
        assert_owned_key(owner_id=str(uuid4()), key=key)
    for invalid in ("../../etc/passwd", "documents/a/b.txt", key + "/../../other"):
        with pytest.raises(PrivateObjectStorageError):
            assert_owned_key(owner_id=owner, key=invalid)
    with pytest.raises(PrivateObjectStorageError):
        object_key(owner_id="../escape", object_id=str(uuid4()), extension=".txt")


@pytest.mark.parametrize("unsafe_endpoint", [
    "http://br-private.aws.neon.tech",
    "https://localhost/",
    "https://169.254.169.254/latest/meta-data",
    "https://br-test.aws.neon.tech.evil.example",
    "https://br-test.aws.neon.tech:8080",
    "https://user:pass@br-test.aws.neon.tech",
    "https://br-test.aws.neon.tech/?secret=123",
])
def test_unsafe_cloud_endpoint_is_rejected(unsafe_endpoint):
    with pytest.raises(ValidationError):
        configured(AWS_ENDPOINT_URL_S3=unsafe_endpoint)


def test_non_neon_region_or_missing_credentials_fail_closed():
    for values in [
        {"AWS_REGION": "localhost"},
        {"AWS_ACCESS_KEY_ID": ""},
        {"AWS_SECRET_ACCESS_KEY": ""},
        {"OBJECT_STORAGE_BUCKET": ""},
    ]:
        with pytest.raises(ValidationError):
            configured(**values)


def test_stream_validation_removes_temporary_file_even_after_success():
    owner = str(uuid4())
    key = object_key(owner_id=owner, object_id=str(uuid4()), extension=".txt")
    blob = "নিরাপদ জ্ঞান".encode("utf-8")
    client = FakeS3(blob)
    path: Path | None = None
    with verified_private_temporary_file(
        owner_id=owner, key=key,
        expected_size=len(blob), expected_sha256=hashlib.sha256(blob).hexdigest(),
        cfg=configured(), client=client,
    ) as temporary:
        path = temporary
        assert path.is_file()
        assert path.read_bytes() == blob
    assert path is not None
    assert not path.exists()
    assert client.reads == [{"Bucket": "private-documents", "Key": key}]


@pytest.mark.parametrize("failure", ["size", "checksum", "invalid_content"])
def test_stream_validation_failures_clean_up_tempfiles(monkeypatch, failure):
    owner = str(uuid4())
    key = object_key(owner_id=owner, object_id=str(uuid4()), extension=".txt")
    blob = b"hello" if failure != "invalid_content" else b"not\x00text"
    paths = []
    # Observe created files without changing the storage production code.
    from app.services import private_object_storage as storage
    real_named = storage.tempfile.NamedTemporaryFile

    def tracked(*args, **kwargs):
        file = real_named(*args, **kwargs)
        paths.append(Path(file.name))
        return file

    monkeypatch.setattr(storage.tempfile, "NamedTemporaryFile", tracked)
    expected_len = len(blob) + (1 if failure == "size" else 0)
    expected_hash = hashlib.sha256(
        b"WRONG" if failure == "checksum" else blob
    ).hexdigest()
    with pytest.raises(PrivateObjectStorageError):
        with verified_private_temporary_file(
            owner_id=owner, key=key, expected_size=expected_len,
            expected_sha256=expected_hash, cfg=configured(), client=FakeS3(blob),
        ):
            pytest.fail("invalid object must not be yielded")
    assert all(not path.exists() for path in paths)


def test_consumer_exception_propagates_and_tempfile_is_removed():
    owner = str(uuid4())
    key = object_key(owner_id=owner, object_id=str(uuid4()), extension=".txt")
    data = b"ok"
    storage_file = None
    with pytest.raises(RuntimeError, match="consumer-failed"):
        with verified_private_temporary_file(
            owner_id=owner, key=key, expected_size=len(data),
            expected_sha256=hashlib.sha256(data).hexdigest(),
            cfg=configured(), client=FakeS3(data),
        ) as path:
            storage_file = path
            raise RuntimeError("consumer-failed")
    assert storage_file is not None and not storage_file.exists()


def test_client_never_sets_public_bucket_acl(monkeypatch):
    from app.services import private_object_storage as module
    observed = {}

    def fake_client(service, **kwargs):
        observed.update(kwargs)
        return service

    monkeypatch.setattr(module.boto3, "client", fake_client)
    assert _client(configured()) == "s3"
    assert observed["endpoint_url"] == _ENDPOINT
    assert observed["config"].signature_version == "s3v4"
    assert observed["config"].s3["addressing_style"] == "path"
    assert "ACL" not in observed
