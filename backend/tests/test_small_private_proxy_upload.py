"""Real upload route contract: verified owner, rollout flag and size limit."""
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.main import app
from app.models.user import User
import app.api.cloud_uploads as api


def _user(email_verified=True):
    return User(
        id=str(uuid4()), email="cloudtest@example.com",
        username="cloudtest", hashed_password="only-test",
        is_active=True,
        email_verified_at=datetime.utcnow() if email_verified else None,
    )


def test_proxy_upload_rejects_anonymous_user(client):
    response = client.post(
        "/api/v1/documents/cloud/proxy",
        files={"file": ("hello.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 401


def test_proxy_does_not_touch_blob_while_disabled(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: _user()
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", False)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", False)

    async def cannot_upload(**kwargs):
        raise AssertionError("No S3 or local write may occur while disabled")

    monkeypatch.setattr(api, "persist_small_private_cloud_upload", cannot_upload)
    response = client.post(
        "/api/v1/documents/cloud/proxy",
        files={"file": ("hello.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 503


def test_proxy_upload_returns_owner_bound_document(client, monkeypatch):
    owner = _user()
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", True)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    expected = b"unique-test-private-data"
    received = []

    async def stored(*, upload, owner, db):
        received.append((owner.id, await upload.read()))
        now = datetime.utcnow()
        return SimpleNamespace(
            id=str(uuid4()), user_id=owner.id,
            original_filename="hello.txt", content_type="text/plain",
            file_extension=".txt", file_size=len(expected),
            checksum_sha256="0" * 64, status="uploaded",
            language=None, page_count=None, word_count=None,
            parsing_quality_score=None, requires_ocr=False,
            error_message=None, created_at=now, updated_at=now,
            processed_at=None,
        )

    monkeypatch.setattr(api, "persist_small_private_cloud_upload", stored)
    response = client.post(
        "/api/v1/documents/cloud/proxy",
        files={"file": ("hello.txt", expected, "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == owner.id
    assert response.json()["status"] == "uploaded"
    assert received == [(owner.id, expected)]


def test_proxy_rejects_provider_failures_without_secret_leak(client, monkeypatch):
    from app.services.private_object_storage import PrivateObjectStorageError
    app.dependency_overrides[get_current_user] = lambda: _user()
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", True)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)

    async def rejects(**kwargs):
        raise PrivateObjectStorageError("secret-url-and-token")

    monkeypatch.setattr(api, "persist_small_private_cloud_upload", rejects)
    response = client.post(
        "/api/v1/documents/cloud/proxy",
        files={"file": ("hello.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 503
    assert "secret-url-and-token" not in response.text
