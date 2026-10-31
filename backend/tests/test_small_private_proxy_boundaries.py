"""Cloud proxy never buffers unverified users or oversized payloads to S3."""
import asyncio
from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.config.settings import settings
from app.models.user import User
from app.services.cloud_proxy_upload import (
    MAX_PROXY_FILE_BYTES, persist_small_private_cloud_upload,
)
from app.services.private_object_storage import PrivateObjectStorageError
from app.services.storage_service import FileTooLargeError, InvalidFileContentError


def _user(*, verified=True):
    return User(
        id=str(uuid4()), email="temp-proxy@example.com",
        username="temp_proxy", hashed_password="test-only",
        is_active=True,
        email_verified_at=datetime.utcnow() if verified else None,
    )


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", True)


def test_unverified_user_rejected_before_file_read(enabled):
    class RejectRead:
        async def read(self, *_args, **_kwargs):
            raise AssertionError("Unverified user may not read uploaded bytes")

    with pytest.raises(PrivateObjectStorageError, match="Verified"):
        asyncio.run(persist_small_private_cloud_upload(
            upload=RejectRead(), owner=_user(verified=False), db=object(),
        ))


def test_size_cap_rejects_before_private_object_write(enabled, monkeypatch):
    import app.services.cloud_proxy_upload as module

    def cannot_access_storage(*_args, **_kwargs):
        raise AssertionError("Oversized file must never reach S3")

    monkeypatch.setattr(module, "_client", cannot_access_storage)
    file = UploadFile(
        filename="payload.txt",
        file=BytesIO(b"a" * (MAX_PROXY_FILE_BYTES + 1)),
    )
    with pytest.raises(FileTooLargeError, match="3 MB"):
        asyncio.run(persist_small_private_cloud_upload(
            upload=file, owner=_user(), db=object(),
        ))


def test_invalid_magic_rejected_before_private_object_write(enabled, monkeypatch):
    import app.services.cloud_proxy_upload as module

    def cannot_access_storage(*_args, **_kwargs):
        raise AssertionError("Malformed content must not reach S3")

    monkeypatch.setattr(module, "_client", cannot_access_storage)
    file = UploadFile(filename="not-really.pdf", file=BytesIO(b"not a PDF"))
    with pytest.raises(InvalidFileContentError):
        asyncio.run(persist_small_private_cloud_upload(
            upload=file, owner=_user(), db=object(),
        ))
