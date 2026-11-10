"""Owner-only recovery requests never queue missing or unverified originals.

All fixtures are synthetic; no private customer files and no live cloud calls.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.main import app
from app.services.private_object_storage import PrivateObjectStorageError
from app.services.document_processing_service import StoredDocumentNotFoundError
import app.api.documents as documents


def _document(owner_id: str, *, storage_path: str, ext: str, status: str = "failed"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=str(uuid4()), user_id=owner_id,
        original_filename="sample" + ext,
        stored_filename=str(uuid4()) + ext,
        storage_path=storage_path,
        content_type="application/pdf" if ext == ".pdf" else "image/png",
        file_extension=ext, file_size=12, checksum_sha256="b" * 64,
        status=status, language=None, page_count=None, word_count=None,
        parsing_quality_score=None, requires_ocr=False,
        error_message="DocumentParsingError", created_at=now, updated_at=now,
        processed_at=now,
    )


def _set_owner_and_doc(monkeypatch, owner, document):
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "KNOWLEDGE_AUTO_INDEX_ENABLED", True)
    monkeypatch.setattr(
        documents, "get_user_document",
        lambda *, db, user_id, document_id: (
            document if user_id == str(owner.id) and document_id == document.id
            else None
        ),
    )


def test_missing_legacy_local_png_keeps_failed_status_and_never_queues(client, monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    doc = _document(str(owner.id), storage_path="lost-local/legacy.png", ext=".png")
    _set_owner_and_doc(monkeypatch, owner, doc)
    monkeypatch.setattr(
        documents, "_resolve_stored_document_path",
        lambda path: (_ for _ in ()).throw(
            StoredDocumentNotFoundError("PRIVATE-STORAGE-PATH")
        ),
    )
    monkeypatch.setattr(
        documents, "enqueue_document",
        lambda **kw: (_ for _ in ()).throw(AssertionError("Must not enqueue")),
    )
    result = client.post(f"/api/v1/documents/{doc.id}/retry-index")
    assert result.status_code == 409
    assert "original file" in result.json()["detail"].lower()
    assert "PRIVATE-STORAGE-PATH" not in result.text
    assert doc.status == "failed"


def test_invalid_cloud_owner_checksum_binding_never_queues(client, monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    doc = _document(str(owner.id), storage_path="cloud://some/path", ext=".pdf")
    _set_owner_and_doc(monkeypatch, owner, doc)
    monkeypatch.setattr(
        documents, "verified_cloud_document_key",
        lambda **kw: (_ for _ in ()).throw(
            PrivateObjectStorageError("PRIVATE-OBJECT-KEY")
        ),
    )
    monkeypatch.setattr(
        documents, "enqueue_document",
        lambda **kw: (_ for _ in ()).throw(AssertionError("Must not enqueue")),
    )
    result = client.post(f"/api/v1/documents/{doc.id}/retry-index")
    assert result.status_code == 409
    assert "PRIVATE-OBJECT-KEY" not in result.text
    assert doc.status == "failed"


def test_completed_owner_cloud_pdf_only_retries_after_verify(client, monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    doc = _document(str(owner.id), storage_path="cloud://verified/key", ext=".pdf")
    _set_owner_and_doc(monkeypatch, owner, doc)
    calls = []

    def verified(**kwargs):
        calls.append("verify")
        assert kwargs["owner_id"] == str(owner.id)
        assert kwargs["document"] is doc
        return "verified/key"

    def enqueue(**kwargs):
        calls.append("queue")
        assert kwargs["owner_id"] == str(owner.id)
        doc.status = "queued"
        return doc

    monkeypatch.setattr(documents, "verified_cloud_document_key", verified)
    monkeypatch.setattr(documents, "enqueue_document", enqueue)
    result = client.post(f"/api/v1/documents/{doc.id}/retry-index")
    assert result.status_code == 200
    assert result.json()["status"] == "queued"
    assert calls == ["verify", "queue"]


def test_nonowner_cannot_test_any_original_or_queue(client, monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    foreign = _document(str(uuid4()), storage_path="cloud://hidden", ext=".pdf")
    _set_owner_and_doc(monkeypatch, owner, foreign)
    monkeypatch.setattr(
        documents, "verified_cloud_document_key",
        lambda **kw: (_ for _ in ()).throw(AssertionError("Unauthorized verify")),
    )
    monkeypatch.setattr(
        documents, "enqueue_document",
        lambda **kw: (_ for _ in ()).throw(AssertionError("Unauthorized retry")),
    )
    result = client.post(f"/api/v1/documents/{foreign.id}/retry-index")
    assert result.status_code == 404
