"""Production K1/K2: durable queue, tenant isolation and honest lexical retrieval."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.document import Document
from app.models.user import User
from app.services import knowledge_index_queue as queue
from app.services import rag_answer_service as rag
from app.embeddings import EmbeddingProviderRequestError
from app.retrieval import RetrievalQuery
from app.services.lexical_retrieval_service import LexicalRetrievalHit


def _user(db, tag):
    user = User(
        username=f"knowledge_{tag}", email=f"knowledge_{tag}@example.org",
        hashed_password="test-only-hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _doc(db, user, tag, ext=".pdf", status="uploaded"):
    obj = Document(
        user_id=str(user.id), original_filename=f"{tag}{ext}",
        stored_filename=f"{uuid4()}{ext}",
        storage_path=f"cloud://documents/{user.id}/{uuid4()}{ext}",
        content_type="application/pdf" if ext == ".pdf" else "image/png",
        file_extension=ext, file_size=3,
        checksum_sha256=uuid4().hex * 2,
        status=status,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_owner_only_queue_and_restart_claim(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_AUTO_INDEX_ENABLED", True)
    alice = _user(db_session, "alice")
    bob = _user(db_session, "bob")
    doc = _doc(db_session, alice, "manual")
    assert queue.enqueue_document(
        db=db_session, owner_id=str(bob.id), document_id=doc.id,
    ) is None
    assert doc.status == "uploaded"
    queued = queue.enqueue_document(
        db=db_session, owner_id=str(alice.id), document_id=doc.id,
    )
    assert queued.status == "queued"
    assert queue.claim_next_document(db_session) == doc.id
    db_session.refresh(doc)
    assert doc.status == "processing"
    assert queue.claim_next_document(db_session) is None


def test_only_documents_are_indexed_and_failed_can_retry(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_AUTO_INDEX_ENABLED", True)
    user = _user(db_session, "image")
    image = _doc(db_session, user, "image", ext=".png")
    assert queue.enqueue_document(
        db=db_session, owner_id=str(user.id), document_id=image.id,
    ).status == "uploaded"
    failed = _doc(db_session, user, "failed", status="failed")
    assert queue.enqueue_document(
        db=db_session, owner_id=str(user.id), document_id=failed.id,
    ).status == "queued"


def test_reclaim_only_stale_processing(db_session):
    user = _user(db_session, "recover")
    old = _doc(db_session, user, "old", status="processing")
    recent = _doc(db_session, user, "recent", status="processing")
    old.updated_at = utc_now_naive() - timedelta(minutes=45)
    db_session.commit()
    assert queue.reclaim_stale_processing(db_session) == 1
    db_session.refresh(old)
    db_session.refresh(recent)
    assert old.status == "queued"
    assert recent.status == "processing"


def test_lexical_fallback_preserves_owner_scoped_pages_without_fake_vectors(
    db_session, monkeypatch,
):
    monkeypatch.setattr(settings, "KNOWLEDGE_LEXICAL_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(
        rag, "search_hybrid_chunks",
        lambda **kw: (_ for _ in ()).throw(
            EmbeddingProviderRequestError("provider down")
        ),
    )
    queries = []

    def lexical(*, db, query):
        queries.append(query)
        return [LexicalRetrievalHit(
            chunk_id="chunk", document_id="doc",
            original_filename="research.pdf",
            parent_chunk_id=None, chunk_role="content",
            chunk_level=0, chunk_index=2,
            source_label="Page 3", section_path=(),
            content="Aqlyra retrieved a real source excerpt.",
            start_page=3, end_page=3, lexical_score=0.65,
        )]

    monkeypatch.setattr(rag, "search_lexical_chunks", lexical)
    query = RetrievalQuery(
        user_id=str(uuid4()), text="Aqlyra research",
        document_ids=("doc",), top_k=4,
    )
    hits = rag._retrieve_rag_hits(db=db_session, query=query)
    assert len(hits) == 1
    assert hits[0].original_filename == "research.pdf"
    assert hits[0].start_page == 3
    assert hits[0].metadata["semantic_similarity_available"] is False
    assert hits[0].metadata["retrieval_mode"] == "lexical_only"
    assert queries[0].document_ids == ("doc",)


def test_explicit_dense_score_cannot_be_bypassed_by_lexical_fallback(
    db_session, monkeypatch,
):
    monkeypatch.setattr(settings, "KNOWLEDGE_LEXICAL_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setattr(
        rag, "search_lexical_chunks",
        lambda **kw: (_ for _ in ()).throw(AssertionError("No search expected")),
    )
    assert rag._retrieve_rag_hits(
        db=db_session,
        query=RetrievalQuery(
            user_id=str(uuid4()), text="query", min_similarity=0.7,
        ),
    ) == []
