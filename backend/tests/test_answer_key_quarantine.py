"""Production QA answer key must not contaminate any RAG retrieval lane.

The answer-key document remains privately owned and is not deleted.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings import DeterministicHashEmbeddingProvider
from app.retrieval import RetrievalQuery
from app.services.lexical_retrieval_service import (
    _fallback_unicode_chunks,
    search_lexical_chunks,
)
from app.services.retrieval_service import (
    score_specific_chunks,
    search_similar_chunks,
)
from app.services.hybrid_retrieval_service import search_hybrid_chunks

ANSWER_KEY = "Aqlyra_RAG_Expected_Answers_DO_NOT_UPLOAD.md"


def _register(client: TestClient):
    reg = client.post("/api/v1/auth/register", json={
        "username": "safeanswerkeyqa",
        "email": "safeanswerkeyqa@example.com",
        "password": "SyntheticOnlyPassword123!",
    })
    assert reg.status_code == 201, reg.text
    auth = client.post("/api/v1/auth/login", json={
        "email": "safeanswerkeyqa@example.com",
        "password": "SyntheticOnlyPassword123!",
    })
    assert auth.status_code == 200, auth.text
    headers = {"Authorization": "Bearer " + auth.json()["access_token"]}
    user = client.get("/api/v1/users/me", headers=headers)
    assert user.status_code == 200, user.text
    return headers, user.json()["id"]


def _upload(client: TestClient, headers, name, content):
    up = client.post("/api/v1/documents/upload", headers=headers, files={
        "file": (name, content.encode("utf-8"), "text/markdown"),
    })
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    process = client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
    assert process.status_code == 200, process.text
    return doc_id


def test_answer_key_quarantined_across_lexical_semantic_hybrid_and_unicode(
    client: TestClient, db_session: Session,
):
    headers, owner_id = _register(client)
    key_id = _upload(
        client, headers, ANSWER_KEY,
        "# Answers\n\nThe Satellite backup is every Sunday 04:00 JST. "
        "京都大学日曜日の記録です。 QA-only answer cheat sheet.",
    )
    manual_id = _upload(
        client, headers, "satellite-real-manual.md",
        "# Original Manual\n\nThe Satellite backup is every Sunday 04:00 JST. "
        "京都大学日曜日の記録です。 Real operator source.",
    )
    assert key_id != manual_id
    # Quarantine is non-destructive: owner can still view the source.
    owned = client.get(f"/api/v1/documents/{key_id}", headers=headers)
    assert owned.status_code == 200
    query = RetrievalQuery(
        user_id=owner_id,
        text="Satellite backup Sunday",
        top_k=10,
        document_ids=(key_id, manual_id),
    )
    semantic = DeterministicHashEmbeddingProvider()
    lexical_hits = search_lexical_chunks(db=db_session, query=query)
    vector_hits = search_similar_chunks(
        db=db_session, query=query, provider=semantic,
    )
    hybrid_hits = search_hybrid_chunks(
        db=db_session, query=query, provider=semantic,
    )
    assert lexical_hits
    assert vector_hits
    assert hybrid_hits
    for hits in (lexical_hits, vector_hits, hybrid_hits):
        assert all(hit.document_id != key_id for hit in hits)
        assert any(hit.document_id == manual_id for hit in hits)

    # Score enrichment must also refuse the quarantined chunk explicitly.
    lexical_keys = search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=owner_id,
            text="Satellite backup Sunday",
            top_k=10,
            document_ids=(key_id,),
        ),
    )
    assert lexical_keys == []
    unicode_hits = _fallback_unicode_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=owner_id,
            text="京都大学日曜日",
            top_k=10,
            document_ids=(key_id, manual_id),
        ),
    )
    assert all(hit.document_id != key_id for hit in unicode_hits)
    assert any(hit.document_id == manual_id for hit in unicode_hits)
