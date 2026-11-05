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
from app.embeddings import DeterministicHashEmbeddingProvider
from app.services.embedding_reindex_service import reindex_missing_document_embeddings


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
    def fake_reindex(*, db, document, provider, max_chunks):
        calls.append(document.id)
        return SimpleNamespace(created_count=1)
    monkeypatch.setattr(mod, "reindex_missing_document_embeddings", fake_reindex)
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
    def fake_reindex(*, db, document, provider, max_chunks):
        calls.append(document.id)
        return SimpleNamespace(created_count=3)
    monkeypatch.setattr(mod, "reindex_missing_document_embeddings", fake_reindex)
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


def test_production_canary_requires_explicit_document_target(
    db_session, monkeypatch,
):
    """Never allow an operator flag to scan every private production document."""
    _active_provider(monkeypatch)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(
        settings, "KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID", "",
    )
    _doc(db_session, "prod-unspecified")
    calls = _record_calls(monkeypatch)
    assert mod.backfill_ready_semantic_embeddings(db=db_session) == 0
    assert calls == []


def test_production_canary_reindexes_only_selected_verified_document(
    db_session, monkeypatch,
):
    _active_provider(monkeypatch)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    _doc(db_session, "other-owner")
    intended = _doc(db_session, "selected-owner")
    monkeypatch.setattr(
        settings, "KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID",
        intended.id,
    )
    calls = _record_calls(monkeypatch)
    assert mod.backfill_ready_semantic_embeddings(db=db_session, limit=3) == 1
    assert calls == [intended.id]


def test_target_does_not_override_verified_cloud_intent_gate(
    db_session, monkeypatch,
):
    _active_provider(monkeypatch)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    unverified = _doc(db_session, "target-invalid", completed=False)
    monkeypatch.setattr(
        settings, "KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID",
        unverified.id,
    )
    calls = _record_calls(monkeypatch)
    assert mod.backfill_ready_semantic_embeddings(db=db_session) == 0
    assert calls == []



def test_incremental_recovery_keeps_current_vectors_and_resumes_per_batch(
    db_session,
):
    """Regression: a large cloud document cannot force an unbounded startup."""
    doc = _doc(db_session, "incremental")
    for n in range(1, 13):
        content = f"Unique test-only indexed text segment number {n}"
        db_session.add(DocumentChunk(
            document_id=doc.id,
            chunk_index=n,
            source_label=f"incremental-{n}",
            content=content,
            embedding_content=content,
            content_hash=sha256(content.encode("utf-8")).hexdigest(),
            token_count=7,
            char_count=len(content),
            word_count=7,
        ))
    db_session.commit()
    provider = DeterministicHashEmbeddingProvider()
    first = reindex_missing_document_embeddings(
        db=db_session, document=doc, provider=provider, max_chunks=8,
    )
    assert first.created_count == 8
    current_before = {
        record.chunk_id: record.id
        for record in db_session.scalars(
            select(EmbeddingRecord).join(DocumentChunk).where(
                DocumentChunk.document_id == doc.id,
            )
        )
    }
    assert len(current_before) == 8
    second = reindex_missing_document_embeddings(
        db=db_session, document=doc, provider=provider, max_chunks=8,
    )
    assert second.created_count == 5
    current_after = {
        record.chunk_id: record.id
        for record in db_session.scalars(
            select(EmbeddingRecord).join(DocumentChunk).where(
                DocumentChunk.document_id == doc.id,
            )
        )
    }
    assert len(current_after) == 13
    assert all(current_after[k] == v for k, v in current_before.items())
    third = reindex_missing_document_embeddings(
        db=db_session, document=doc, provider=provider, max_chunks=8,
    )
    assert third.created_count == 0
    assert third.replaced_count == 0


def test_incremental_repair_replaces_stale_hash_only(db_session):
    doc = _doc(db_session, "stale-repair")
    chunk = db_session.scalar(select(DocumentChunk).where(
        DocumentChunk.document_id == doc.id,
    ))
    _vector(db_session, chunk, stale=True)
    provider = DeterministicHashEmbeddingProvider()
    result = reindex_missing_document_embeddings(
        db=db_session, document=doc, provider=provider,
    )
    assert result.created_count == 1
    # A separate-model stale vector remains intact (model-version isolation).
    others = list(db_session.scalars(
        select(EmbeddingRecord).where(EmbeddingRecord.chunk_id == chunk.id)
    ))
    assert len(others) == 2
    assert any(row.content_hash == chunk.content_hash for row in others)
    assert any(row.content_hash != chunk.content_hash for row in others)


def test_incremental_recovery_rejects_unbounded_batch(db_session):
    doc = _doc(db_session, "invalid-batch")
    provider = DeterministicHashEmbeddingProvider()
    for n in (0, 25):
        try:
            reindex_missing_document_embeddings(
                db=db_session, document=doc, provider=provider, max_chunks=n,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Unbounded recovery was accepted")
