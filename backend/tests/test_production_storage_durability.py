"""Prevent irreversible file loss when production has only an ephemeral disk."""
import asyncio
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException, UploadFile
import pytest

import app.api.artifacts as artifact_api
import app.api.documents as document_api
from app.config.settings import settings
from app.services import artifact_storage
from app.services.storage_durability_policy import (
    artifact_writes_permitted, local_writes_permitted,
)


@pytest.fixture
def ephemeral_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED", False)
    monkeypatch.setattr(settings, "EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED", False)


def test_ephemeral_production_disallows_new_local_writes(ephemeral_production):
    assert not local_writes_permitted()
    assert not artifact_writes_permitted()


def test_verified_persistent_local_mount_can_be_opted_in(
    ephemeral_production, monkeypatch,
):
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED", True)
    assert local_writes_permitted()
    assert artifact_writes_permitted()


def test_core_does_not_fake_remote_artifact_support(ephemeral_production):
    assert not artifact_writes_permitted()


def test_development_local_uploads_remain_usable(ephemeral_production, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    assert local_writes_permitted()
    assert artifact_writes_permitted()


def test_upload_denied_before_processing_or_db_persistence(
    ephemeral_production, monkeypatch,
):
    async def unexpected_upload(*args, **kwargs):
        raise AssertionError("Ephemeral file write must not be attempted")

    monkeypatch.setattr(
        document_api, "save_upload_to_temporary_storage", unexpected_upload
    )
    upload = UploadFile(filename="private.txt", file=BytesIO(b"Private data"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(document_api.upload_document(
            file=upload, current_user=SimpleNamespace(id=uuid4()), db=object(),
        ))
    assert exc.value.status_code == 503
    assert "Durable document storage" in exc.value.detail


def test_ai_generation_fails_before_calling_paid_provider(
    ephemeral_production, monkeypatch,
):
    def unexpected_llm(*args, **kwargs):
        raise AssertionError("AI provider must not be called")

    monkeypatch.setattr(artifact_api, "create_configured_llm_provider", unexpected_llm)
    with pytest.raises(HTTPException) as exc:
        artifact_api.generate(
            request=artifact_api.GenerateArtifactRequest(
                prompt="Generate a useful two-page summary",
                title="Summary", format="pdf",
            ),
            current_user=SimpleNamespace(id=uuid4()), db=object(),
        )
    assert exc.value.status_code == 503
    assert "Durable artifact storage" in exc.value.detail


def test_render_fails_before_creating_ephemeral_file(
    ephemeral_production, monkeypatch,
):
    def unexpected_save(**kwargs):
        raise AssertionError("Ephemeral artifact must not be written")

    monkeypatch.setattr(artifact_api, "create_artifact", unexpected_save)
    with pytest.raises(HTTPException) as exc:
        artifact_api.render(
            request=artifact_api.RenderArtifactRequest(
                title="Private", content="Hello", format="docx"
            ),
            current_user=SimpleNamespace(id=uuid4()),
        )
    assert exc.value.status_code == 503


def test_direct_artifact_storage_calls_also_fail_closed(ephemeral_production):
    with pytest.raises(artifact_storage.ArtifactStorageError) as exc:
        artifact_storage.create_artifact(
            user_id=str(uuid4()), title="X", kind="md", content="Secret",
            provider_name="test", source_document_ids=[], citation_count=0,
        )
    assert "Durable artifact storage" in str(exc.value)


@pytest.mark.parametrize(
    ("kind", "signature"),
    [
        ("docx", b"PK"),
        ("xlsx", b"PK"),
        ("pptx", b"PK"),
        ("pdf", b"%PDF"),
        ("md", b"# Temporary"),
    ],
)
def test_explicit_ephemeral_artifact_mode_generates_owner_scoped_files(
    ephemeral_production, tmp_path, monkeypatch, kind, signature,
):
    # The test mode is specifically for disposable artifacts, not uploads.
    monkeypatch.setattr(settings, "EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED", True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    assert artifact_writes_permitted()
    assert not local_writes_permitted()

    owner = str(uuid4())
    another_user = str(uuid4())
    item = artifact_storage.create_artifact(
        user_id=owner,
        title="Temporary test file",
        kind=kind,
        content="# Temporary test file\n\nAqlyra artifact smoke test.",
        provider_name="local-smoke-test",
        source_document_ids=[],
        citation_count=0,
    )
    result = artifact_storage.artifact_download(
        user_id=owner, artifact_id=item["id"]
    )
    assert result is not None
    path, metadata = result
    assert path.read_bytes().startswith(signature)
    assert metadata["format"] == kind
    assert artifact_storage.artifact_download(
        user_id=another_user, artifact_id=item["id"]
    ) is None
    assert artifact_storage.delete_artifact(
        user_id=owner, artifact_id=item["id"]
    )
    assert artifact_storage.artifact_download(
        user_id=owner, artifact_id=item["id"]
    ) is None


def test_temporary_artifact_mode_still_blocks_document_uploads(
    ephemeral_production, monkeypatch,
):
    monkeypatch.setattr(settings, "EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED", True)
    assert artifact_writes_permitted()
    assert not local_writes_permitted()
    # Auth/RAG document uploads stay behind the original durable storage gate.
    async def unexpected_upload(*args, **kwargs):
        raise AssertionError("No production document upload is allowed")

    monkeypatch.setattr(
        document_api, "save_upload_to_temporary_storage", unexpected_upload
    )
    upload = UploadFile(filename="private.txt", file=BytesIO(b"Private data"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(document_api.upload_document(
            file=upload, current_user=SimpleNamespace(id=uuid4()), db=object(),
        ))
    assert exc.value.status_code == 503
