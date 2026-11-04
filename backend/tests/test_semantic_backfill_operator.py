"""Operator backfill never selects unverified or foreign cloud documents."""
from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

import app.services.knowledge_semantic_backfill as mod
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.models.user import User


def _doc(db, suffix, *, completed=True, ext=".pdf", with_chunk=True):
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
    if with_chunk:
        text = f"Synthetic semantic coverage check for {suffix}"
        db.add(DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            source_label=f"test-{suffix}",
            content=text,
            embedding_content=text,
            content_hash=sha256(text.encode("utf-8")).hexdigest(),
            token_count=6,
            char_count=len(text),
            word_count=6,
        ))
        db.commit()
    return doc


def _active_provider(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "remote_onnx")
    monkeypatch.setattr(
        mod, "create_configured_embedding_provider",
        lambda: SimpleNamespace(info=SimpleNamespace(
            provider_name="remote_onnx",
            model_name="bekko-static-multilingual-int8-mrl384-v1",
            dimension=384,
        )),
    )


def _vector(db, chunk, *, stale=False):
    db.add(EmbeddingRecord(
        chunk_id=chunk.id,
        provider_name="remote_onnx",
        model_name="bekko-static-multilingual-int8-mrl384-v1",
        dimension=384,
        embedding=[0.0] * 383 + [1.0],
        content_hash="0" * 64 if stale else chunk.content_hash,
        input_token_count=chunk.token_count,
    ))
    db.commit()


def _record_calls(monkeypatch):
    calls = []
    def fake_reindex(*, db, document, provider):
        calls.append(document.id)
        return SimpleNamespace(created_count=1)
    monkeypatch.setattr(mod, "reindex_document_embeddings", fake_reindex)
    return calls


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
            model_name="bekko-static-multilingual-int8-mrl384-v1",
            dimension=384,
        )),
    )
    def fake_reindex(*, db, document, provider):
        calls.append(document.id)
        return SimpleNamespace(created_count=3)
    monkeypatch.setattr(mod, "reindex_document_embeddings", fake_reindex)
    assert mod.backfill_ready_semantic_embeddings(db=db_session, limit=1) == 1
    assert calls == [valid.id]


def test_partial_vector_coverage_needs_repair_even_with_one_valid_row(
    db_session, monkeypatch,
):
    """An existing vector for chunk #0 must never mask missing chunk #1."""
    _active_provider(monkeypatch)
    complete = _doc(db_session, "complete")
    partial = _doc(db_session, "partial")
    complete_chunk = db_session.scalar(select(DocumentChunk).where(
        DocumentChunk.document_id == complete.id,
    ))
    partial_chunk = db_session.scalar(select(DocumentChunk).where(
        DocumentChunk.document_id == partial.id,
    ))
    _vector(db_session, complete_chunk)
    _vector(db_session, partial_chunk)
    text = "Unindexed second private paragraph"
    db_session.add(DocumentChunk(
        document_id=partial.id,
        chunk_index=1,
        source_label="partial-second",
        content=text,
        embedding_content=text,
        content_hash=sha256(text.encode("utf-8")).hexdigest(),
        token_count=4,
        char_count=len(text),
        word_count=4,
    ))
    db_session.commit()
    calls = _record_calls(monkeypatch)
    assert mod.backfill_ready_semantic_embeddings(db=db_session, limit=1) == 1
    assert calls == [partial.id]


def test_stale_content_hash_is_repaired_without_touching_complete_doc(
    db_session, monkeypatch,
):
    _active_provider(monkeypatch)
    complete = _doc(db_session, "current")
    stale = _doc(db_session, "stale")
    for doc, is_stale in ((complete, False), (stale, True)):
        chunk = db_session.scalar(select(DocumentChunk).where(
            DocumentChunk.document_id == doc.id,
        ))
        _vector(db_session, chunk, stale=is_stale)
    calls = _record_calls(monkeypatch)
    assert mod.backfill_ready_semantic_embeddings(db=db_session, limit=1) == 1
    assert calls == [stale.id]


def test_ready_document_without_chunks_is_skipped(
    db_session, monkeypatch,
):
    _active_provider(monkeypatch)
    _doc(db_session, "empty", with_chunk=False)
    calls = _record_calls(monkeypatch)
    assert mod.backfill_ready_semantic_embeddings(db=db_session) == 0
    assert calls == []
