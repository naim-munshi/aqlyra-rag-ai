"""Synthetic provider probe cannot read or delete any existing user data."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from app.services.private_storage_probe import (
    PrivateStorageProbeError,
    run_private_storage_probe,
)


class DummyPrivateS3:
    def __init__(self, *, corrupt=False, fail_put=False, fail_delete=False):
        self.objects = {"documents/user-id/legacy.pdf": b"do-not-touch"}
        self.actions = []
        self.corrupt = corrupt
        self.fail_put = fail_put
        self.fail_delete = fail_delete

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.actions.append(("put", Key))
        assert Bucket == "private-documents"
        assert Key.startswith("ops/aqlyra-storage-probes/")
        assert ContentType == "application/octet-stream"
        if self.fail_put:
            raise RuntimeError("sensitive endpoint and credentials")
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        self.actions.append(("get", Key))
        assert Key.startswith("ops/aqlyra-storage-probes/")
        data = self.objects[Key]
        return {"Body": BytesIO(b"tampered" if self.corrupt else data),
                "ContentLength": len(data)}

    def delete_object(self, *, Bucket, Key):
        self.actions.append(("delete", Key))
        assert Key.startswith("ops/aqlyra-storage-probes/")
        if self.fail_delete:
            raise RuntimeError("private URL leaked if printed")
        self.objects.pop(Key, None)

    def head_object(self, *, Bucket, Key):
        self.actions.append(("head", Key))
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"},
                               "ResponseMetadata": {"HTTPStatusCode": 404}},
                              "HeadObject")
        return {"ContentLength": len(self.objects[Key])}


@pytest.mark.parametrize("mode", ["success", "corrupt", "fail_put", "fail_delete"])
def test_isolated_private_storage_probe_never_touches_user_objects(mode):
    s3 = DummyPrivateS3(
        corrupt=mode == "corrupt",
        fail_put=mode == "fail_put",
        fail_delete=mode == "fail_delete",
    )
    config = SimpleNamespace(OBJECT_STORAGE_BUCKET="private-documents")
    if mode == "success":
        run_private_storage_probe(cfg=config, client=s3)
    else:
        with pytest.raises(PrivateStorageProbeError) as caught:
            run_private_storage_probe(cfg=config, client=s3)
        assert str(caught.value) == "Private S3 probe failed"
        assert "sensitive" not in str(caught.value)
        assert "URL" not in str(caught.value)
    assert s3.objects["documents/user-id/legacy.pdf"] == b"do-not-touch"
    assert all(key.startswith("ops/aqlyra-storage-probes/") for _, key in s3.actions)
    assert len({key for _, key in s3.actions}) == 1
    if mode in ("success", "corrupt"):
        assert not any(key.startswith("ops/") for key in s3.objects)


def test_probe_rejects_missing_bucket_before_any_provider_call():
    with pytest.raises(PrivateStorageProbeError):
        run_private_storage_probe(
            cfg=SimpleNamespace(OBJECT_STORAGE_BUCKET=""), client=DummyPrivateS3()
        )
