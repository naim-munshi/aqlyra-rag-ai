"""Realistic security acceptance for direct 50MiB private cloud uploads."""
from types import SimpleNamespace
from uuid import uuid4

from app.config.settings import Settings
from app.services.private_cors_setup import configure_private_upload_cors
from app.services.private_object_storage import prepare_private_upload


class FakeStorage:
    def __init__(self, prior=None):
        self.rules = list(prior or [])
        self.puts = 0
        self.signed = []

    def get_bucket_cors(self, **kwargs):
        assert kwargs["Bucket"] == "aqlyra-private"
        return {"CORSRules": self.rules}

    def put_bucket_cors(self, **kwargs):
        assert kwargs["Bucket"] == "aqlyra-private"
        self.rules = kwargs["CORSConfiguration"]["CORSRules"]
        self.puts += 1

    def generate_presigned_url(self, *args, **kwargs):
        self.signed.append(kwargs)
        return (
            "https://br-test.storage.c-2.us-east-2.aws.neon.tech/"
            "aqlyra-private/documents/test/file.pdf?X-Amz-Signature=test"
        )


def _cfg():
    return Settings(
        _env_file=None, PRIVATE_OBJECT_STORAGE_ENABLED=True,
        AWS_ENDPOINT_URL_S3="https://br-test.storage.c-2.us-east-2.aws.neon.tech",
        AWS_REGION="us-east-2", AWS_ACCESS_KEY_ID="synthetic",
        AWS_SECRET_ACCESS_KEY="synthetic", OBJECT_STORAGE_BUCKET="aqlyra-private",
        MAX_UPLOAD_SIZE_MB=50,
    )


def test_safe_bucket_cors_only_adds_production_put_and_preserves_prior():
    existing = {"ID":"existing-read-rule", "AllowedOrigins":["https://old.example.org"],
                "AllowedMethods":["GET"],"AllowedHeaders":["x-test"]}
    store = FakeStorage([existing])
    configure_private_upload_cors(storage=store, cfg=_cfg())
    assert store.rules[0] == existing
    assert store.rules[1]["AllowedOrigins"] == ["https://aqlyra-ai.vercel.app"]
    assert store.rules[1]["AllowedMethods"] == ["PUT"]
    assert store.rules[1]["AllowedHeaders"] == ["content-type"]
    assert store.puts == 1
    configure_private_upload_cors(storage=store, cfg=_cfg())
    assert store.puts == 2
    assert len(store.rules) == 2


def test_exactly_50_mib_signed_cloud_upload_supported_and_larger_rejected():
    from app.services.private_object_storage import PrivateObjectStorageError
    storage = FakeStorage()
    cfg = _cfg()
    requested = prepare_private_upload(
        owner_id=str(uuid4()), filename="big.pdf",
        size_bytes=50 * 1024 * 1024, cfg=cfg, client=storage,
    )
    assert requested.expires_in_seconds == 600
    assert storage.signed[0]["ExpiresIn"] == 600
    try:
        prepare_private_upload(
            owner_id=str(uuid4()), filename="too-big.pdf",
            size_bytes=50 * 1024 * 1024 + 1, cfg=cfg, client=storage,
        )
    except PrivateObjectStorageError:
        pass
    else:
        raise AssertionError("50MiB limit was bypassed")
