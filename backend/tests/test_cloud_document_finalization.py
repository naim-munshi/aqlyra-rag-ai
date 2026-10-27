"""Internal finalization and recovery; no live Neon credentials are used."""
import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.user import User
from app.services.cloud_document_finalization import (
    CloudFinalizationConflict,
    claim_with_reserved_final_key,
    commit_verified_cloud_document,
    finalize_cloud_upload,
    list_stale_claimed_uploads,
    recover_promoted_cloud_document,
)
from app.services.cloud_upload_intent_service import reserve_upload_intent
from app.services.private_object_storage import PrivateObjectStorageError


ENDPOINT = "https://br-private-example.storage.c-2.us-east-2.aws.neon.tech"


def configured(**kwargs):
    opts = {
        "PRIVATE_OBJECT_STORAGE_ENABLED": True,
        "AWS_ENDPOINT_URL_S3": ENDPOINT,
        "AWS_REGION": "us-east-2",
        "AWS_ACCESS_KEY_ID": "private-test-key",
        "AWS_SECRET_ACCESS_KEY": "private-test-secret",
        "OBJECT_STORAGE_BUCKET": "private-documents",
    }
    opts.update(kwargs)
    return Settings(_env_file=None, **opts)


class InMemoryS3:
    def __init__(self, data=b"cloud content"):
        self.data = data
        self.objects = {}
        self.requests = []
        self.fail_final_write = False
        self.bad_final_get = False

    def generate_presigned_url(self, method, **kwargs):
        key = kwargs["Params"]["Key"]
        self.objects[key] = self.data  # Fake a browser PUT after grant.
        return f"{ENDPOINT}/private-documents/{key}?X-Amz-Signature=fake"

    def get_object(self, *, Bucket, Key):
        self.requests.append(("GET", Key))
        if Key not in self.objects:
            raise KeyError("object not present")
        data = self.objects[Key]
        if self.bad_final_get and Key.startswith("final/"):
            data = b"X" + data[1:]

        class Body:
            def __init__(self):
                self.closed = False

            def iter_chunks(self, chunk_size):
                for start in range(0, len(data), chunk_size):
                    yield data[start:start + chunk_size]

            def close(self):
                self.closed = True

        return {"ContentLength": len(data), "Body": Body()}

    def put_object(self, **kwargs):
        self.requests.append(("PUT", kwargs["Key"]))
        if self.fail_final_write:
            raise RuntimeError("PRIVATE_STORAGE_SECRET_ERROR")
        assert kwargs["Key"].startswith("final/documents/")
        assert "ACL" not in kwargs
        self.objects[kwargs["Key"]] = kwargs["Body"].read()

    def delete_object(self, *, Bucket, Key):
        self.requests.append(("DELETE", Key))
        self.objects.pop(Key, None)


def make_user(client: TestClient, db: Session, label: str):
    suffix = uuid4().hex[:8]
    user_info = {
        "username": f"cloud_{label}_{suffix}",
        "email": f"cloud_{label}_{suffix}@example.com",
        "password": "TestSafePass123!",
    }
    registered = client.post("/api/v1/auth/register", json=user_info)
    assert registered.status_code == 201, registered.text
    owner = db.scalar(select(User).where(User.email == user_info["email"]))
    assert owner is not None and owner.email_verified_at is not None
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user_info["email"], "password": user_info["password"]},
    )
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    return owner, headers


def reserve(db: Session, owner: User, store: InMemoryS3):
    return reserve_upload_intent(
        db=db, owner=owner,
        original_filename="report.txt",
        expected_size=len(store.data),
        expected_sha256=hashlib.sha256(store.data).hexdigest(),
        cfg=configured(), client=store,
    )


def test_claim_persists_recovery_key_before_remote_writes(
    client: TestClient, db_session: Session,
):
    owner, _ = make_user(client, db_session, "claim")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    result = claim_with_reserved_final_key(
        db=db_session, owner=owner,
        intent_id=grant.intent_id, cfg=configured(),
    )
    assert result and result.status == "claimed"
    assert result.final_object_key.startswith("final/documents/" + owner.id + "/")
    assert db_session.get(CloudUploadIntent, grant.intent_id).final_object_key == result.final_object_key
    assert all(not k.startswith("final/") for k in store.objects)
    assert claim_with_reserved_final_key(
        db=db_session, owner=owner, intent_id=grant.intent_id, cfg=configured(),
    ) is None
    assert db_session.query(Document).count() == 0


def test_full_internal_finalize_writes_document_once_and_links_intent(
    client: TestClient, db_session: Session,
):
    owner, headers = make_user(client, db_session, "main")
    store = InMemoryS3()
    issued = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=issued.intent_id,
        cfg=configured(), client=store,
    )
    intent = db_session.get(CloudUploadIntent, issued.intent_id)
    assert intent and intent.status == "completed"
    assert intent.document_id == result.document_id
    assert intent.final_object_key == result.final_object_key
    doc = db_session.get(Document, result.document_id)
    assert doc and doc.storage_path == "cloud://" + result.final_object_key
    assert doc.user_id == owner.id
    assert doc.file_size == len(store.data)
    assert doc.checksum_sha256 == hashlib.sha256(store.data).hexdigest()
    assert store.objects[result.final_object_key] == store.data
    assert any(kind == "GET" and key == result.final_object_key for kind, key in store.requests)
    with pytest.raises(CloudFinalizationConflict):
        recover_promoted_cloud_document(
            db=db_session, owner=owner,
            intent_id=issued.intent_id, cfg=configured(), client=store,
        )
    assert db_session.query(Document).count() == 1

    # Legacy handler must never delete the DB record while leaking cloud bytes.
    delete = client.delete(
        f"/api/v1/documents/{doc.id}", headers=headers,
    )
    assert delete.status_code == 409
    assert db_session.get(Document, doc.id) is not None
    assert client.get(
        f"/api/v1/documents/{doc.id}/content", headers=headers,
    ).status_code == 409
    assert client.post(
        f"/api/v1/documents/{doc.id}/process", headers=headers,
    ).status_code == 409
    # A second tenant cannot resolve even the existence of the document.
    other, other_headers = make_user(client, db_session, "other")
    assert other.id != owner.id
    assert client.get(
        f"/api/v1/documents/{doc.id}", headers=other_headers,
    ).status_code == 404
    assert client.delete(
        f"/api/v1/documents/{doc.id}", headers=other_headers,
    ).status_code == 404


def test_crash_between_remote_copy_and_db_commit_is_recoverable(
    client: TestClient, db_session: Session,
):
    owner, _ = make_user(client, db_session, "crash")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    claimed = claim_with_reserved_final_key(
        db=db_session, owner=owner, intent_id=grant.intent_id, cfg=configured(),
    )
    assert claimed and claimed.final_object_key
    # Simulate power failure AFTER remote object exists, BEFORE DB insert.
    store.objects[claimed.final_object_key] = store.data
    db_session.expire_all()
    recovered = recover_promoted_cloud_document(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(), client=store,
    )
    assert recovered.recovered is True
    assert recovered.final_object_key == claimed.final_object_key
    assert db_session.query(Document).count() == 1
    assert db_session.get(CloudUploadIntent, grant.intent_id).status == "completed"
    assert all(kind != "PUT" for kind, _ in store.requests)


def test_recovery_rejects_absent_or_tampered_remote_final(
    client: TestClient, db_session: Session,
):
    owner, _ = make_user(client, db_session, "unverified")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    claim = claim_with_reserved_final_key(
        db=db_session, owner=owner, intent_id=grant.intent_id, cfg=configured(),
    )
    assert claim and claim.final_object_key
    with pytest.raises(PrivateObjectStorageError):
        recover_promoted_cloud_document(
            db=db_session, owner=owner, intent_id=grant.intent_id,
            cfg=configured(), client=store,
        )
    assert db_session.query(Document).count() == 0
    assert db_session.get(CloudUploadIntent, grant.intent_id).status == "claimed"
    store.objects[claim.final_object_key] = b"tampered bytes"
    with pytest.raises(PrivateObjectStorageError):
        recover_promoted_cloud_document(
            db=db_session, owner=owner, intent_id=grant.intent_id,
            cfg=configured(), client=store,
        )
    assert db_session.query(Document).count() == 0
    assert db_session.get(CloudUploadIntent, grant.intent_id).status == "claimed"


def test_remote_write_failure_retains_claim_reference_and_no_document(
    client: TestClient, db_session: Session,
):
    owner, _ = make_user(client, db_session, "failure")
    store = InMemoryS3()
    store.fail_final_write = True
    grant = reserve(db_session, owner, store)
    with pytest.raises(PrivateObjectStorageError) as error:
        finalize_cloud_upload(
            db=db_session, owner=owner, intent_id=grant.intent_id,
            cfg=configured(), client=store,
        )
    assert "PRIVATE_STORAGE_SECRET" not in str(error.value)
    saved = db_session.get(CloudUploadIntent, grant.intent_id)
    assert saved and saved.status == "claimed" and saved.final_object_key
    assert db_session.query(Document).count() == 0


def test_duplicate_content_does_not_commit_second_document(
    client: TestClient, db_session: Session,
):
    owner, _ = make_user(client, db_session, "duplicates")
    first_store = InMemoryS3()
    first_grant = reserve(db_session, owner, first_store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=first_grant.intent_id,
        cfg=configured(), client=first_store,
    )
    second_store = InMemoryS3()
    second_grant = reserve(db_session, owner, second_store)
    with pytest.raises(CloudFinalizationConflict, match="already exists"):
        finalize_cloud_upload(
            db=db_session, owner=owner, intent_id=second_grant.intent_id,
            cfg=configured(), client=second_store,
        )
    assert db_session.query(Document).count() == 1
    assert db_session.get(CloudUploadIntent, first_grant.intent_id).document_id == result.document_id
    second = db_session.get(CloudUploadIntent, second_grant.intent_id)
    assert second.status == "claimed" and second.final_object_key


def test_other_owner_cannot_claim_or_recover(
    client: TestClient, db_session: Session,
):
    owner, _ = make_user(client, db_session, "owner")
    other, _ = make_user(client, db_session, "outsider")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    assert claim_with_reserved_final_key(
        db=db_session, owner=other, intent_id=grant.intent_id,
        cfg=configured(),
    ) is None
    claim_with_reserved_final_key(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(),
    )
    with pytest.raises(CloudFinalizationConflict):
        recover_promoted_cloud_document(
            db=db_session, owner=other, intent_id=grant.intent_id,
            cfg=configured(), client=store,
        )


def test_stale_scan_is_read_only_and_bounded(client: TestClient, db_session: Session):
    owner, _ = make_user(client, db_session, "scan")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    assert claim_with_reserved_final_key(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(),
    ) is not None
    row = db_session.get(CloudUploadIntent, grant.intent_id)
    row.claimed_at = utc_now_naive() - timedelta(minutes=30)
    db_session.commit()
    old = list_stale_claimed_uploads(db=db_session)
    assert any(x.id == grant.intent_id for x in old)
    assert db_session.get(CloudUploadIntent, grant.intent_id).status == "claimed"
    with pytest.raises(ValueError):
        list_stale_claimed_uploads(db=db_session, limit=1000)


def test_disabled_feature_is_fail_closed(client: TestClient, db_session: Session):
    owner, _ = make_user(client, db_session, "disabled")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    with pytest.raises(PrivateObjectStorageError, match="disabled"):
        claim_with_reserved_final_key(
            db=db_session, owner=owner, intent_id=grant.intent_id,
            cfg=configured(PRIVATE_OBJECT_STORAGE_ENABLED=False),
        )
    assert db_session.get(CloudUploadIntent, grant.intent_id).status == "issued"


def test_private_cloud_download_uses_owner_checked_45s_redirect(
    client: TestClient, db_session: Session, monkeypatch,
):
    from app.config.settings import settings
    from app.services.cloud_document_access import private_document_read_grant

    owner, headers = make_user(client, db_session, "download")
    other, other_headers = make_user(client, db_session, "not_owner")
    store = InMemoryS3()
    issued = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=issued.intent_id,
        cfg=configured(), client=store,
    )
    document = db_session.get(Document, result.document_id)
    assert document is not None

    class ReadGrantStore:
        def generate_presigned_url(self, method, **kwargs):
            assert method == "get_object"
            assert kwargs["ExpiresIn"] == 45
            assert kwargs["HttpMethod"] == "GET"
            assert kwargs["Params"]["Key"] == result.final_object_key
            assert kwargs["Params"]["ResponseContentDisposition"] == "attachment"
            return f"{ENDPOINT}/private-documents/{result.final_object_key}?X-Amz-Signature=read"

    grant = private_document_read_grant(
        db=db_session, owner_id=owner.id, document=document,
        cfg=configured(), client=ReadGrantStore(),
    )
    assert grant.startswith(ENDPOINT)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL_S3", ENDPOINT)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    from app.services import cloud_document_access
    monkeypatch.setattr(cloud_document_access, "_client", lambda _cfg: ReadGrantStore())

    response = client.get(
        f"/api/v1/documents/{document.id}/content",
        headers=headers, follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == grant
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get(
        f"/api/v1/documents/{document.id}/content",
        headers=other_headers, follow_redirects=False,
    ).status_code == 404
    assert client.get(
        f"/api/v1/documents/{document.id}/content",
        follow_redirects=False,
    ).status_code == 401

    # Inconsistent DB metadata must never yield a signed URL.
    document.content_type = "application/octet-stream"
    db_session.commit()
    assert client.get(
        f"/api/v1/documents/{document.id}/content",
        headers=headers, follow_redirects=False,
    ).status_code == 409


def test_cloud_process_uses_verified_short_lived_scratch(
    client: TestClient, db_session: Session, monkeypatch,
):
    from app.config.settings import settings
    from app.services import cloud_process_io

    owner, headers = make_user(client, db_session, "processing")
    outsider, outsider_headers = make_user(client, db_session, "processing_other")
    store = InMemoryS3(b"AI retrieval can ground answers in documents.")
    grant = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(), client=store,
    )
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(cloud_process_io, "_client", lambda cfg: store)

    url = f"/api/v1/documents/{result.document_id}/process"
    assert client.post(url, headers=outsider_headers).status_code == 404
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    doc = db_session.get(Document, result.document_id)
    assert doc is not None and doc.status == "ready"
    assert doc.storage_path.startswith("cloud://")
    assert client.post(url, headers=headers).status_code == 409
    assert outsider.id != owner.id


def test_cloud_process_rejects_corrupt_remote_without_parsing(
    client: TestClient, db_session: Session, monkeypatch,
):
    from app.config.settings import settings
    from app.services import cloud_process_io

    owner, headers = make_user(client, db_session, "bad_cloud")
    store = InMemoryS3(b"healthy remote text")
    grant = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(), client=store,
    )
    store.bad_final_get = True
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(cloud_process_io, "_client", lambda cfg: store)
    res = client.post(
        f"/api/v1/documents/{result.document_id}/process", headers=headers,
    )
    assert res.status_code == 409
    assert db_session.get(Document, result.document_id).status == "uploaded"


def test_private_cloud_prepare_finalize_api_is_explicitly_gated(
    client: TestClient, db_session: Session, monkeypatch,
):
    from app.config.settings import settings
    from app.services import private_object_storage, private_object_promotion
    owner, headers = make_user(client, db_session, "api")
    outsider, other_headers = make_user(client, db_session, "api_other")
    store = InMemoryS3(b"verified full cloud text")
    blob = store.data
    payload = {
        "filename": "report.txt",
        "size_bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }
    endpoint = "/api/v1/documents/cloud/prepare"
    assert client.post(endpoint, json=payload, headers=headers).status_code == 404
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PUBLIC_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL_S3", ENDPOINT)
    monkeypatch.setattr(private_object_storage, "_client", lambda _cfg: store)
    monkeypatch.setattr(private_object_promotion, "_client", lambda _cfg: store)

    assert client.post(endpoint, json=payload).status_code == 401
    prepared = client.post(endpoint, json=payload, headers=headers)
    assert prepared.status_code == 201, prepared.text
    grant = prepared.json()
    assert grant["method"] == "PUT"
    assert grant["expires_in_seconds"] == 120
    assert grant["headers"] == {"Content-Type": "text/plain"}
    assert "X-Amz-Signature" in grant["upload_url"]
    finalize = f"/api/v1/documents/cloud/{grant['intent_id']}/finalize"
    assert client.post(finalize, headers=other_headers).status_code == 409
    completed = client.post(finalize, headers=headers)
    assert completed.status_code == 201, completed.text
    assert db_session.get(Document, completed.json()["document_id"]) is not None
    assert client.post(finalize, headers=headers).status_code == 409
    assert owner.id != outsider.id


def test_cloud_document_delete_is_owner_bound_and_remote_first(
    client: TestClient, db_session: Session, monkeypatch,
):
    from app.config.settings import settings
    from app.services import cloud_document_deletion

    owner, headers = make_user(client, db_session, "delete")
    other, foreign_headers = make_user(client, db_session, "foreign_delete")
    store = InMemoryS3(b"temporary cloud document")
    grant = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(), client=store,
    )
    assert result.final_object_key in store.objects
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(cloud_document_deletion, "_client", lambda cfg: store)
    url = f"/api/v1/documents/{result.document_id}"
    assert client.delete(url, headers=foreign_headers).status_code == 404
    assert client.delete(url, headers=headers).status_code == 204
    assert db_session.get(Document, result.document_id) is None
    assert result.final_object_key not in store.objects
    assert client.delete(url, headers=headers).status_code == 404
    assert other.id != owner.id


def test_failed_remote_cloud_delete_preserves_document(
    client: TestClient, db_session: Session, monkeypatch,
):
    from app.config.settings import settings
    from app.services import cloud_document_deletion

    owner, headers = make_user(client, db_session, "delete_failure")
    store = InMemoryS3()
    grant = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(), client=store,
    )
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(cloud_document_deletion, "_client", lambda cfg: store)
    original = store.delete_object

    def fail_delete(**kwargs):
        raise RuntimeError("private-provider-credential-message")

    store.delete_object = fail_delete
    url = f"/api/v1/documents/{result.document_id}"
    failed = client.delete(url, headers=headers)
    assert failed.status_code == 503
    assert "credential" not in failed.text
    assert db_session.get(Document, result.document_id) is not None
    assert result.final_object_key in store.objects

    store.delete_object = original
    assert client.delete(url, headers=headers).status_code == 204
    assert db_session.get(Document, result.document_id) is None
