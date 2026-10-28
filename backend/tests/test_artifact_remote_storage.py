"""Opt-in S3 artifacts: owner isolation, restart persistence, integrity, quota.

All network/storage calls are fake; NEVER use live user files or credentials.
"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from hashlib import sha256
from threading import Lock
from uuid import uuid4

import pytest

from app.config.settings import settings
from app.services import artifact_remote_storage as remote
from app.services import artifact_storage as facade


class MissingObject(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class FakePrivateBucket:
    def __init__(self):
        self.objects = {}
        self.fail_metadata = False

    def put_object(self, *, Bucket, Key, Body, ContentType):
        assert Bucket == "private-documents"
        assert Key.startswith("artifacts/")
        assert ContentType
        if self.fail_metadata and Key.endswith(".json"):
            raise RuntimeError("provider-secret-must-not-leak")
        self.objects[Key] = bytes(Body)

    def get_object(self, *, Bucket, Key):
        assert Bucket == "private-documents"
        if Key not in self.objects:
            raise MissingObject()
        data = self.objects[Key]
        return {"Body": BytesIO(data), "ContentLength": len(data)}

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys, **kwargs):
        assert Bucket == "private-documents"
        assert MaxKeys > 0 and "ContinuationToken" not in kwargs
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        return {"Contents": [{"Key": key} for key in keys], "IsTruncated": False}

    def delete_object(self, *, Bucket, Key):
        assert Bucket == "private-documents"
        self.objects.pop(Key, None)


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    bucket = FakePrivateBucket()
    mutex = Lock()

    @contextmanager
    def locked(_owner):
        with mutex:
            yield

    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(settings, "ARTIFACT_REMOTE_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "ARTIFACT_METADATA_HMAC_KEY", "ci-artifact-metadata-independent-hmac-key-2026-safe")
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(remote, "_storage", lambda: bucket)
    monkeypatch.setattr(remote, "_owner_lock", locked)
    return bucket


def _make(owner, *, title="Secure research", kind="md"):
    return facade.create_artifact(
        user_id=owner, title=title, kind=kind, content="# Proof\nOwner-private text",
        provider_name="test", source_document_ids=[], citation_count=0,
    )


def test_private_artifacts_owner_scope_survive_process_restart(private_store, tmp_path):
    first, second = str(uuid4()), str(uuid4())
    item = _make(first)
    assert item["filename"].endswith(".md")
    assert "sha256" not in item
    assert len(facade.list_artifacts(user_id=first)) == 1
    assert facade.list_artifacts(user_id=second) == []
    assert facade.read_artifact(user_id=second, artifact_id=item["id"]) is None
    assert facade.artifact_download(user_id=second, artifact_id=item["id"]) is None
    assert not facade.delete_artifact(user_id=second, artifact_id=item["id"])

    # Simulated new API process: no local files, same remote bucket.
    assert not (tmp_path / "artifact-workspace").exists()
    data, metadata = facade.artifact_download(user_id=first, artifact_id=item["id"])
    assert data == b"# Proof\nOwner-private text"
    assert metadata["id"] == item["id"]
    assert facade.delete_artifact(user_id=first, artifact_id=item["id"])
    assert facade.read_artifact(user_id=first, artifact_id=item["id"]) is None



def test_remote_metadata_hmac_prevents_rewritten_file_and_checksum(private_store):
    owner = str(uuid4())
    artifact = _make(owner)
    binary = remote._key(owner, artifact["id"], "md")
    meta_key = remote._key(owner, artifact["id"], "json")
    original = json.loads(private_store.objects[meta_key])
    assert original["signature_version"] == 1
    assert len(original["metadata_signature"]) == 64
    assert "metadata_signature" not in artifact
    assert "signature_version" not in artifact

    # A bucket write key alone must not allow forging the file+SHA pair.
    tampered_bytes = b"# Replaced without signing secret"
    private_store.objects[binary] = tampered_bytes
    original["sha256"] = sha256(tampered_bytes).hexdigest()
    private_store.objects[meta_key] = json.dumps(original).encode()
    assert facade.read_artifact(user_id=owner, artifact_id=artifact["id"]) is None
    assert facade.artifact_download(user_id=owner, artifact_id=artifact["id"]) is None
    summary = remote.audit_owner_inventory(user_id=owner)
    assert summary["invalid_metadata"] == 1
    assert summary["complete_records"] == 0


def test_remote_metadata_hmac_binds_owner_scope(private_store):
    first, second = str(uuid4()), str(uuid4())
    artifact = _make(first)
    private_store.objects[
        remote._key(second, artifact["id"], "json")
    ] = private_store.objects[remote._key(first, artifact["id"], "json")]
    private_store.objects[
        remote._key(second, artifact["id"], "md")
    ] = private_store.objects[remote._key(first, artifact["id"], "md")]
    assert facade.read_artifact(user_id=second, artifact_id=artifact["id"]) is None
    summary = remote.audit_owner_inventory(user_id=second)
    assert summary["invalid_metadata"] == 1
    assert summary["complete_records"] == 0
    assert facade.read_artifact(user_id=first, artifact_id=artifact["id"])



def test_private_bytes_fail_sha256_integrity(private_store):
    owner = str(uuid4())
    item = _make(owner)
    key = remote._key(owner, item["id"], "md")
    private_store.objects[key] = b"# Evil\nOwner-private text"
    with pytest.raises(facade.ArtifactStorageError, match="integrity"):
        facade.artifact_download(user_id=owner, artifact_id=item["id"])


def test_remote_owner_quota_atomic_across_workers(private_store, monkeypatch):
    owner = str(uuid4())
    monkeypatch.setattr(remote, "MAX_ARTIFACTS_PER_USER", 2)

    def attempt(number):
        try:
            _make(owner, title=f"Artifact {number}")
            return True
        except facade.ArtifactQuotaError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count(True) == 2
    assert results.count(False) == 10
    assert len(facade.list_artifacts(user_id=owner)) == 2


def test_failed_remote_write_never_falls_back_to_local_disk(private_store, tmp_path):
    owner = str(uuid4())
    private_store.fail_metadata = True
    with pytest.raises(facade.ArtifactStorageError) as error:
        _make(owner)
    assert "provider-secret" not in str(error.value)
    assert facade.list_artifacts(user_id=owner) == []
    assert not (tmp_path / "artifact-workspace").exists()
    assert private_store.objects == {}


def test_remote_setting_requires_private_storage():
    from app.config.settings import Settings
    base = settings.model_dump()
    base.update(ARTIFACT_REMOTE_STORAGE_ENABLED=True,
                PRIVATE_OBJECT_STORAGE_ENABLED=False)
    with pytest.raises(ValueError, match="Remote artifacts require private"):
        Settings(**base)


def test_remote_advisory_lock_uses_scoped_postgres_transaction(monkeypatch):
    events = []
    class Db:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        @contextmanager
        def begin(self):
            events.append("begin")
            yield
            events.append("commit")
        def execute(self, sql, args):
            assert "pg_advisory_xact_lock" in str(sql)
            assert isinstance(args["key"], int)
            events.append("lock")

    monkeypatch.setattr(remote, "SessionLocal", lambda: Db())
    with remote._owner_lock(str(uuid4())):
        events.append("write")
    assert events == ["begin", "lock", "write", "commit"]


def test_private_artifacts_http_auth_and_download(private_store, client):
    url = "/api/v1/artifacts"
    assert client.get(url).status_code == 401

    def login(username):
        email = username + "@example.com"
        register = client.post("/api/v1/auth/register", json={
            "username": username, "email": email, "password": "SecurePass123!",
        })
        assert register.status_code == 201
        result = client.post("/api/v1/auth/login", json={
            "email": email, "password": "SecurePass123!",
        })
        assert result.status_code == 200
        return {"Authorization": "Bearer " + result.json()["access_token"]}

    alpha = login("remotetestalpha")
    beta = login("remotetestbeta")
    created = client.post(url + "/render", headers=alpha, json={
        "title": "Report", "format": "md", "content": "# Remote proof",
    })
    assert created.status_code == 201
    artifact_id = created.json()["id"]
    assert client.get(url, headers=beta).json()["total"] == 0
    assert client.get(url + "/" + artifact_id, headers=beta).status_code == 404
    assert client.get(url + "/" + artifact_id + "/download", headers=beta).status_code == 404
    assert client.get(url + "/not-a-uuid", headers=alpha).status_code == 404

    download = client.get(url + "/" + artifact_id + "/download", headers=alpha)
    assert download.status_code == 200
    assert download.content == b"# Remote proof"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert client.delete(url + "/" + artifact_id, headers=alpha).status_code == 204
    assert client.get(url + "/" + artifact_id, headers=alpha).status_code == 404


@pytest.mark.parametrize("kind", ["md", "pdf", "docx", "xlsx", "pptx"])
def test_all_remote_artifact_formats_round_trip(private_store, kind):
    owner = str(uuid4())
    item = _make(owner, title="Five format proof", kind=kind)
    binary, returned = facade.artifact_download(
        user_id=owner, artifact_id=item["id"],
    )
    assert returned["format"] == kind
    assert len(binary) == item["size"]
    if kind == "md":
        assert binary.startswith(b"# Proof")
    elif kind == "pdf":
        assert binary.startswith(b"%PDF")
    else:
        assert binary.startswith(b"PK")
    assert facade.delete_artifact(user_id=owner, artifact_id=item["id"])



def test_real_postgresql_owner_advisory_lock_is_cross_session(db_session):
    """Check a real PG16/PG18 lock; not a fake threading mutex."""
    from hashlib import sha256
    from sqlalchemy import text as sql_text
    from app.database.connection import SessionLocal

    owner = str(uuid4())
    signed_key = int.from_bytes(
        sha256(("aqlyra/artifact/quota/" + owner).encode()).digest()[:8],
        byteorder="big", signed=True,
    )
    with remote._owner_lock(owner):
        with SessionLocal() as independent:
            with independent.begin():
                assert independent.execute(
                    sql_text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": signed_key},
                ).scalar_one() is False

    # Releasing the first transaction makes the key available again.
    with SessionLocal() as independent:
        with independent.begin():
            assert independent.execute(
                sql_text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": signed_key},
            ).scalar_one() is True


def test_remote_owner_inventory_counts_only_and_never_modifies_objects(private_store):
    owner, unrelated = str(uuid4()), str(uuid4())
    missing = _make(owner, title="Missing binary")
    orphan = _make(owner, title="Orphan binary")
    foreign = _make(unrelated, title="Foreign record")

    private_store.objects.pop(remote._key(owner, missing["id"], "md"))
    private_store.objects.pop(remote._key(owner, orphan["id"], "json"))
    private_store.objects[remote._key(owner, str(uuid4()), "json")] = b"{bad-json"
    private_store.objects[remote._prefix(owner) + "unsafe-untracked"] = b"secret"

    before = dict(private_store.objects)
    report = remote.audit_owner_inventory(user_id=owner)
    assert report == {
        "complete_records": 0,
        "missing_binaries": 1,
        "invalid_metadata": 1,
        "orphan_binaries": 1,
        "unexpected_keys": 1,
        "total_objects": 4,
    }
    assert private_store.objects == before

    # Audit is scoped by the server-supplied UUID, not arbitrary S3 keys.
    assert remote.audit_owner_inventory(user_id=unrelated) == {
        "complete_records": 1,
        "missing_binaries": 0,
        "invalid_metadata": 0,
        "orphan_binaries": 0,
        "unexpected_keys": 0,
        "total_objects": 2,
    }
    assert foreign["id"] not in str(report)
    assert owner not in str(report)
    assert "secret" not in str(report)



def test_remote_owner_inventory_pagination_is_complete(private_store, monkeypatch):
    owner = str(uuid4())
    record = _make(owner)
    metadata = remote._key(owner, record["id"], "json")
    binary = remote._key(owner, record["id"], "md")
    seen = []

    def paged(*, Bucket, Prefix, MaxKeys, **kwargs):
        assert Bucket == "private-documents"
        assert Prefix == remote._prefix(owner)
        assert MaxKeys == 1000
        seen.append(kwargs.get("ContinuationToken"))
        if "ContinuationToken" not in kwargs:
            return {
                "Contents": [{"Key": binary}],
                "IsTruncated": True, "NextContinuationToken": "next",
            }
        assert kwargs["ContinuationToken"] == "next"
        return {
            "Contents": [{"Key": metadata}],
            "IsTruncated": False,
        }

    monkeypatch.setattr(private_store, "list_objects_v2", paged)
    report = remote.audit_owner_inventory(user_id=owner)
    assert report["complete_records"] == 1
    assert report["orphan_binaries"] == 0
    assert report["total_objects"] == 2
    assert seen == [None, "next"]


def test_remote_owner_inventory_fails_on_broken_pagination(private_store, monkeypatch):
    monkeypatch.setattr(private_store, "list_objects_v2", lambda **kwargs: {
        "IsTruncated": True, "Contents": [],
    })
    with pytest.raises(remote.RemoteArtifactError, match="continuation"):
        remote.audit_owner_inventory(user_id=str(uuid4()))



def test_remote_owner_inventory_fails_closed_on_s3_error(private_store, monkeypatch):
    def provider_error(**kwargs):
        raise RuntimeError("secret-neon-endpoint-and-password")
    monkeypatch.setattr(private_store, "list_objects_v2", provider_error)
    with pytest.raises(remote.RemoteArtifactError) as exc:
        remote.audit_owner_inventory(user_id=str(uuid4()))
    assert "secret-neon" not in str(exc.value)


def test_remote_owner_inventory_rejects_invalid_owner(private_store):
    with pytest.raises(remote.RemoteArtifactError, match="Invalid artifact identifier"):
        remote.audit_owner_inventory(user_id="../../foreign")
