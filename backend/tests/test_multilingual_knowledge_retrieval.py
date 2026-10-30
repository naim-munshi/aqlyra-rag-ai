"""K2 multilingual lexical fallback must be grounded and tenant-isolated."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.retrieval import RetrievalQuery
from app.services.lexical_retrieval_service import (
    _unicode_search_terms,
    search_lexical_chunks,
)


def _account(client: TestClient, tag: str):
    email = f"unicode-rag-{tag}@example.org"
    user = f"unicode_rag_{tag}"
    register = client.post("/api/v1/auth/register", json={
        "username": user, "email": email, "password": "TestPass123!",
    })
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "TestPass123!",
    })
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/users/me", headers=headers)
    assert profile.status_code == 200
    return profile.json()["id"], headers


def _index(client: TestClient, headers, name: str, text: str):
    response = client.post("/api/v1/documents/upload", headers=headers, files={
        "file": (name, ("# Source\n\n" + text).encode(), "text/markdown"),
    })
    assert response.status_code == 201, response.text
    doc_id = response.json()["id"]
    processed = client.post(
        f"/api/v1/documents/{doc_id}/process", headers=headers,
    )
    assert processed.status_code == 200, processed.text
    return doc_id


def test_japanese_substring_retrieval_with_same_owner_and_page_sources(
    client: TestClient, db_session: Session,
):
    alice, ah = _account(client, "jp-alice")
    bob, bh = _account(client, "jp-bob")
    doc_id = _index(
        client, ah, "japanese.md",
        "東京工芸大学情報システム研究室ではAIの検索技術を研究しています。",
    )
    other_id = _index(
        client, bh, "other.md",
        "東京工芸大学の研究室は機密情報を記録しています。",
    )
    hits = search_lexical_chunks(db_session, RetrievalQuery(
        user_id=alice, text="東京工芸大学の研究室",
        document_ids=(doc_id,), top_k=5,
    ))
    assert hits
    assert all(h.document_id == doc_id for h in hits)
    assert all(h.original_filename == "japanese.md" for h in hits)
    assert search_lexical_chunks(db_session, RetrievalQuery(
        user_id=alice, text="機密情報",
        document_ids=(other_id,), top_k=5,
    )) == []


def test_bengali_inflection_and_no_cross_tenant_leak(
    client: TestClient, db_session: Session,
):
    owner, oh = _account(client, "bn-owner")
    intruder, ih = _account(client, "bn-intruder")
    d = _index(
        client, oh, "bangla.md",
        "তথ্যপ্রযুক্তি গবেষণায় তথ্য অনুসন্ধানের নির্ভুলতা গুরুত্বপূর্ণ।",
    )
    hits = search_lexical_chunks(db_session, RetrievalQuery(
        user_id=owner, text="তথ্যপ্রযুক্তির গবেষণা",
        document_ids=(d,), top_k=8,
    ))
    assert hits
    assert all(h.document_id == d for h in hits)
    assert search_lexical_chunks(db_session, RetrievalQuery(
        user_id=intruder, text="তথ্যপ্রযুক্তির গবেষণা",
        document_ids=(d,), top_k=8,
    )) == []


def test_unicode_queries_are_bounded_and_do_not_escape_sql_patterns():
    terms = _unicode_search_terms("日本語の研究%%%%__" * 30)
    assert len(terms) <= 16
    assert terms
    assert all("%" not in term and "_" not in term for term in terms)
