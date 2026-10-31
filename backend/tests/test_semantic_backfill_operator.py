"""Operator backfill never selects unverified or foreign cloud documents."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import app.services.knowledge_semantic_backfill as mod
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.user import User


def _doc(db, suffix, *, completed=True, ext=".pdf"):
    u = User(
        username=f"semantic_{suffix}",
        email=f"semantic_{suffix}@example.org",
        hashed_password="test-hash",
    )
    db.add(u)
    db.flush()
    key = f"documents/{u.id}/{uuid4().hex}{ext}"
    checksum = uuid4().hex * 2
    doc = Document(
        user_id=str(u.id), original_filename=f"file{ext}",
        stored_filename=f"{uuid4().hex}{ext}",
        storage_path="cloud://" + key,
        content_type="application/pdf" if ext == ".pdf" else "image/png",
        file_extension=ext, file_size=3, checksum_sha256=checksum,
        status="ready",
    )
    db.add(doc)
    db.flush()
    if completed:
        db.add(CloudUploadIntent(
            user_id=str(u.id),
            object_key=f"staging/{u.id}/{uuid4().hex}",
            original_filename=doc.original_filename,
            content_type=doc.content_type,
            expected_size=3, expected_sha256=checksum,
            status="completed",
            completed_at=utc_now_naive(),
            expires_at=utc_now_naive() + timedelta(hours=1),
            final_object_key=key,
            document_id=doc.id,
        ))
    db.commit()
    return doc


def test_semantic_reindex_default_off(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP", False)
    assert mod.backfill_ready_semantic_embeddings(db=db_session) == 0


def test_reindexes_only_owner_linked_ready_cloud_knowledge(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "remote_onnx")
    valid = _doc(db_session, "verified")
    _doc(db_session, "no_intent", completed=False)
    _doc(db_session, "image", ext=".png")
    calls = []
    monkeypatch.setattr(
        mod, "create_configured_embedding_provider",
        lambda: SimpleNamespace(info=SimpleNamespace(
            provider_name="remote_onnx",
            model_name="multilingual-e5-small-int8-v1",
            dimension=384,
        )),
    )
    def fake_reindex(*, db, document, provider):
        calls.append(document.id)
        return SimpleNamespace(created_count=3)
    monkeypatch.setattr(mod, "reindex_document_embeddings", fake_reindex)
    assert mod.backfill_ready_semantic_embeddings(db=db_session, limit=1) == 1
    assert calls == [valid.id]
