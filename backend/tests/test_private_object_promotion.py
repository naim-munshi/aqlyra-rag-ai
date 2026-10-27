"""Isolated final-object promotion tests; no Neon credentials or live uploads."""
import hashlib
from uuid import uuid4

import pytest

from app.config.settings import Settings
from app.services.private_object_promotion import (
    assert_owned_final_key,
    discard_promoted_private_object,
    final_object_key,
    promote_verified_private_upload,
)
from app.services.private_object_storage import (
    PrivateObjectStorageError,
    object_key,
)

ENDPOINT = "https://br-private-example.storage.c-2.us-east-2.aws.neon.tech"


def storage_settings(**changes):
    data = {
        "PRIVATE_OBJECT_STORAGE_ENABLED": True,
        "AWS_ENDPOINT_URL_S3": ENDPOINT,
        "AWS_REGION": "us-east-2",
        "AWS_ACCESS_KEY_ID": "internal-test-access",
        "AWS_SECRET_ACCESS_KEY": "internal-test-secret",
        "OBJECT_STORAGE_BUCKET": "private-documents",
    }
    data.update(changes)
    return Settings(_env_file=None, **data)


class FakeObjectStore:
    def __init__(self):
        self.objects = {}
        self.operations = []
        self.fail_put = False
        self.fail_final_get = False
        self.corrupt_final = False
        self.fail_delete = False
        self.reads = []

    def get_object(self, *, Bucket, Key):
        self.operations.append(("get", Key))
        if Key.startswith("final/") and self.fail_final_get:
            raise RuntimeError("SECRET_PROVIDER_DETAILS")
        data = self.objects[Key]
        if Key.startswith("final/") and self.corrupt_final:
            data = b"X" + data[1:]

        class Body:
            closed = False

            def iter_chunks(self, chunk_size):
                for start in range(0, len(data), chunk_size):
                    yield data[start:start + chunk_size]

            def close(self):
                self.closed = True

        b = Body()
        self.reads.append(b)
        return {"ContentLength": len(data), "Body": b}

    def put_object(self, **kwargs):
        self.operations.append(("put", kwargs["Key"]))
        if self.fail_put:
            raise RuntimeError("SECRET_UPLOAD_PROVIDER_DETAILS")
        assert "ACL" not in kwargs
        assert "ExpiresIn" not in kwargs
        assert "ContentLength" in kwargs
        payload = kwargs["Body"].read()
        assert len(payload) == kwargs["ContentLength"]
        self.objects[kwargs["Key"]] = payload

    def delete_object(self, *, Bucket, Key):
        self.operations.append(("delete", Key))
        if self.fail_delete:
            raise RuntimeError("SECRET_DELETION_PROVIDER_DETAILS")
        self.objects.pop(Key, None)


def arranged(data=b"hello cloud"):
    owner = str(uuid4())
    stage = object_key(
        owner_id=owner, object_id=str(uuid4()), extension=".txt",
    )
    store = FakeObjectStore()
    store.objects[stage] = data
    return owner, stage, store


def promote(owner, stage, store, data=b"hello cloud", cfg=None):
    return promote_verified_private_upload(
        owner_id=owner,
        staging_key=stage,
        expected_size=len(data),
        expected_sha256=hashlib.sha256(data).hexdigest(),
        cfg=cfg or storage_settings(),
        client=store,
    )


def test_promotion_writes_new_unshared_key_and_verifies_bytes():
    data = b"hello cloud"
    owner, stage, store = arranged(data)
    result = promote(owner, stage, store, data)
    assert result.key.startswith(f"final/documents/{owner}/")
    assert result.key != stage
    assert result.key not in [key for kind, key in store.operations if kind == "get"][:1]
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.size_bytes == len(data)
    assert store.objects[result.key] == data
    assert store.objects[stage] == data  # No silent deletion before DB commit.
    assert [action for action, _ in store.operations] == [
        "get", "put", "get",
    ]
    assert all(body.closed for body in store.reads if body.closed is not None)


def test_two_promotions_use_distinct_final_keys():
    owner, stage, store = arranged()
    first = promote(owner, stage, store)
    second = promote(owner, stage, store)
    assert first.key != second.key
    assert first.key in store.objects and second.key in store.objects


def test_cross_tenant_staging_key_never_reaches_store():
    owner, stage, store = arranged()
    other = str(uuid4())
    with pytest.raises(PrivateObjectStorageError, match="not owned"):
        promote(other, stage, store)
    assert store.operations == []


def test_bad_checksum_blocks_write_and_keeps_stage():
    owner, stage, store = arranged()
    with pytest.raises(PrivateObjectStorageError, match="checksum mismatch"):
        promote_verified_private_upload(
            owner_id=owner, staging_key=stage, expected_size=11,
            expected_sha256="a" * 64, cfg=storage_settings(), client=store,
        )
    assert all(kind != "put" for kind, _ in store.operations)
    assert list(store.objects) == [stage]


def test_wrong_size_blocks_write_and_keeps_stage():
    owner, stage, store = arranged()
    with pytest.raises(PrivateObjectStorageError, match="size mismatch"):
        promote_verified_private_upload(
            owner_id=owner, staging_key=stage, expected_size=10,
            expected_sha256=hashlib.sha256(b"hello cloud").hexdigest(),
            cfg=storage_settings(), client=store,
        )
    assert all(kind != "put" for kind, _ in store.operations)
    assert list(store.objects) == [stage]


def test_invalid_file_content_blocks_promotion():
    owner, stage, store = arranged(b"bad\x00binary")
    with pytest.raises(PrivateObjectStorageError):
        promote(owner, stage, store, b"bad\x00binary")
    assert all(kind != "put" for kind, _ in store.operations)


@pytest.mark.parametrize("which", ["put", "read", "corrupt"])
def test_failure_cleans_final_key_and_does_not_reveal_secrets(which):
    owner, stage, store = arranged()
    if which == "put":
        store.fail_put = True
    elif which == "read":
        store.fail_final_get = True
    else:
        store.corrupt_final = True

    with pytest.raises(PrivateObjectStorageError) as error:
        promote(owner, stage, store)
    assert "SECRET" not in str(error.value)
    assert [kind for kind, _ in store.operations][-1] == "delete"
    assert list(store.objects) == [stage]


def test_cleanup_failure_raises_sanitized_error_and_needs_orphan_recovery():
    owner, stage, store = arranged()
    store.corrupt_final = True
    store.fail_delete = True
    with pytest.raises(PrivateObjectStorageError) as error:
        promote(owner, stage, store)
    assert "SECRET" not in str(error.value)
    assert stage in store.objects
    assert any(k.startswith("final/") for k in store.objects)
    # A process crash or failed compensating delete needs a sweeper; the
    # public upload workflow stays OFF until that exists.


def test_compensating_delete_validates_owner_and_final_prefix():
    owner, stage, store = arranged()
    result = promote(owner, stage, store)
    other = str(uuid4())
    with pytest.raises(PrivateObjectStorageError):
        discard_promoted_private_object(
            owner_id=other, final_key=result.key, cfg=storage_settings(),
            client=store,
        )
    with pytest.raises(PrivateObjectStorageError):
        discard_promoted_private_object(
            owner_id=owner, final_key=stage, cfg=storage_settings(),
            client=store,
        )
    assert result.key in store.objects
    discard_promoted_private_object(
        owner_id=owner, final_key=result.key, cfg=storage_settings(),
        client=store,
    )
    assert result.key not in store.objects
    assert stage in store.objects


def test_invalid_final_paths_are_rejected():
    owner = str(uuid4())
    final = final_object_key(
        owner_id=owner, object_id=str(uuid4()), extension=".md",
    )
    assert assert_owned_final_key(owner_id=owner, key=final) == ".md"
    for bad in (
        final + "/../overwrite",
        final.replace(owner, str(uuid4())),
        final.replace("/documents/", "/other/"),
        final.replace(".md", ".exe"),
    ):
        with pytest.raises(PrivateObjectStorageError):
            assert_owned_final_key(owner_id=owner, key=bad)


def test_disabled_storage_rejects_promotion_and_cleanup():
    owner, stage, store = arranged()
    cfg = storage_settings(PRIVATE_OBJECT_STORAGE_ENABLED=False)
    with pytest.raises(PrivateObjectStorageError, match="Invalid private upload"):
        promote(owner, stage, store, cfg=cfg)
    final = final_object_key(
        owner_id=owner, object_id=str(uuid4()), extension=".txt",
    )
    with pytest.raises(PrivateObjectStorageError, match="disabled"):
        discard_promoted_private_object(
            owner_id=owner, final_key=final, cfg=cfg, client=store,
        )
    assert store.operations == []
