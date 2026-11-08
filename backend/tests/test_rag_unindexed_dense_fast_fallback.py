"""PostgreSQL proof: lexical-only Knowledge never invokes cold semantic worker.

No production data, external LLM or semantic service is used.
"""
from hashlib import sha256
from uuid import uuid4

import pytest

from app.config.settings import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.models.user import User
from app.retrieval import RetrievalQuery
from app.services import rag_answer_service as rag
from app.services.knowledge_dense_coverage import scope_has_current_dense_vectors
from app.embeddings.remote_semantic_provider import MODEL


def _owned_chunk(db, tag):
    owner = User(
        username=f"fastpath_{tag}", email=f"fastpath_{tag}@example.org",
        hashed_password="synthetic-fixture-not-a-real-password",
    )
    db.add(owner)
    db.flush()
    text = f"QuantumFalcon handbook revision policy for {tag}."
    doc = Document(
        user_id=str(owner.id), original_filename=f"{tag}.md",
        stored_filename=f"{uuid4().hex}.md",
        storage_path=f"cloud://documents/{owner.id}/{uuid4().hex}.md",
        file_extension=".md", content_type="text/markdown",
        file_size=len(text), checksum_sha256=sha256(text.encode()).hexdigest(),
        status="ready",
    )
    db.add(doc)
    db.flush()
    chunk = DocumentChunk(
        document_id=doc.id, chunk_index=0, source_label="Synthetic rule",
        content=text, embedding_content=text,
        content_hash=sha256(text.encode()).hexdigest(),
        token_count=7, char_count=len(text), word_count=7,
    )
    db.add(chunk)
    db.commit()
    return owner, doc, chunk


def _enable(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_LEXICAL_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_SKIP_DENSE_WHEN_UNINDEXED_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "remote_onnx")
    monkeypatch.setattr(settings, "RAG_QUERY_REWRITE_ENABLED", False)
    monkeypatch.setattr(settings, "RAG_RERANKER_ENABLED", False)


def _query(owner_id, doc_id, *, min_similarity=None):
    return RetrievalQuery(
        user_id=str(owner_id), text="QuantumFalcon handbook revision",
        document_ids=(str(doc_id),), top_k=5,
        min_similarity=min_similarity,
    )


def test_unindexed_ready_document_uses_real_lexical_hits_immediately(
    db_session, monkeypatch,
):
    _enable(monkeypatch)
    owner, doc, chunk = _owned_chunk(db_session, "bare")
    monkeypatch.setattr(
        rag, "_retrieve_with_optional_reranking",
        lambda **kwargs: pytest.fail("Remote query embedding must not run"),
    )
    query = _query(owner.id, doc.id)
    assert not scope_has_current_dense_vectors(db=db_session, query=query)
    hits = rag._retrieve_rag_hits(db=db_session, query=query)
    assert hits
    assert hits[0].chunk_id == chunk.id
    assert hits[0].metadata["retrieval_mode"] == "lexical_only"
    assert hits[0].metadata["semantic_similarity_available"] is False
    assert hits[0].similarity_score == 0.0


def test_foreign_embeddings_never_count_for_current_owner(
    db_session, monkeypatch,
):
    _enable(monkeypatch)
    first, doc1, chunk1 = _owned_chunk(db_session, "first")
    second, doc2, chunk2 = _owned_chunk(db_session, "second")
    db_session.add(EmbeddingRecord(
        chunk_id=chunk2.id, provider_name="remote_onnx",
        model_name=MODEL, dimension=384,
        content_hash=chunk2.content_hash,
        embedding=[0.0] * 383 + [1.0],
        input_token_count=chunk2.token_count,
    ))
    db_session.commit()
    assert not scope_has_current_dense_vectors(
        db=db_session, query=_query(first.id, doc1.id),
    )
    assert not scope_has_current_dense_vectors(
        db=db_session, query=_query(first.id, doc2.id),
    )
    assert scope_has_current_dense_vectors(
        db=db_session, query=_query(second.id, doc2.id),
    )
    assert rag._retrieve_rag_hits(
        db=db_session, query=_query(first.id, doc2.id),
    ) == []


def test_stale_vector_is_not_considered_semantically_usable(
    db_session, monkeypatch,
):
    _enable(monkeypatch)
    owner, doc, chunk = _owned_chunk(db_session, "stale")
    db_session.add(EmbeddingRecord(
        chunk_id=chunk.id, provider_name="remote_onnx",
        model_name=MODEL, dimension=384,
        content_hash="0" * 64,
        embedding=[0.0] * 383 + [1.0],
        input_token_count=chunk.token_count,
    ))
    db_session.commit()
    assert not scope_has_current_dense_vectors(
        db=db_session, query=_query(owner.id, doc.id),
    )


def test_dense_path_preserved_when_current_vector_exists(
    db_session, monkeypatch,
):
    _enable(monkeypatch)
    owner, doc, chunk = _owned_chunk(db_session, "indexed")
    db_session.add(EmbeddingRecord(
        chunk_id=chunk.id, provider_name="remote_onnx",
        model_name=MODEL, dimension=384,
        content_hash=chunk.content_hash,
        embedding=[0.0] * 383 + [1.0],
        input_token_count=chunk.token_count,
    ))
    db_session.commit()
    observed = []

    def fake_dense(**kwargs):
        observed.append(kwargs["retrieval_query"].user_id)
        return ["dense-path-kept"]

    monkeypatch.setattr(rag, "_retrieve_with_optional_reranking", fake_dense)
    hits = rag._retrieve_rag_hits(
        db=db_session, query=_query(owner.id, doc.id),
    )
    assert hits == ["dense-path-kept"]
    assert observed == [str(owner.id)]


def test_min_similarity_never_silently_downgraded(
    db_session, monkeypatch,
):
    _enable(monkeypatch)
    owner, doc, chunk = _owned_chunk(db_session, "threshold")
    monkeypatch.setattr(
        rag, "_retrieve_with_optional_reranking",
        lambda **kwargs: pytest.fail("Dense must not run without any vector"),
    )
    hits = rag._retrieve_rag_hits(
        db=db_session,
        query=_query(owner.id, doc.id, min_similarity=0.7),
    )
    assert hits == []


def test_feature_off_preserves_current_routing(db_session, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(settings, "KNOWLEDGE_SKIP_DENSE_WHEN_UNINDEXED_ENABLED", False)
    owner, doc, chunk = _owned_chunk(db_session, "disabled")
    monkeypatch.setattr(
        rag, "_retrieve_with_optional_reranking",
        lambda **kwargs: ["existing-dense-routing"],
    )
    assert rag._retrieve_rag_hits(
        db=db_session, query=_query(owner.id, doc.id),
    ) == ["existing-dense-routing"]
