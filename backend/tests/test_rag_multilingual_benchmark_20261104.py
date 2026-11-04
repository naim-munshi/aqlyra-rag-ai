"""Isolated multilingual RAG retrieval/ACL benchmark using real PostgreSQL.

Not a real Groq/Tavily or live semantic-worker benchmark: fixtures are
synthetic documents and deterministic test embeddings. Never label these
scores as actual production RAG accuracy.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.retrieval import RetrievalQuery
from app.retrieval.evaluation import RetrievalEvaluationCase, evaluate_rankings
from app.services.lexical_retrieval_service import search_lexical_chunks


def _identity(client: TestClient, tag: str):
    email = f"rag-benchmark-{tag}@example.com"
    user = f"ragbench_{tag}"
    registered = client.post(
        "/api/v1/auth/register",
        json={"username": user, "email": email, "password": "TestPass123!"},
    )
    assert registered.status_code == 201, registered.text
    authenticated = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    assert authenticated.status_code == 200, authenticated.text
    headers = {
        "Authorization": f"Bearer {authenticated.json()['access_token']}"
    }
    user_id = client.get("/api/v1/users/me", headers=headers).json()["id"]
    return user_id, headers


def _document(client: TestClient, headers, name: str, content: str) -> str:
    uploaded = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (name, ("# Knowledge\n\n" + content).encode(), "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    doc_id = uploaded.json()["id"]
    indexed = client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=headers,
    )
    assert indexed.status_code == 200, indexed.text
    return doc_id


def test_postgres_english_bengali_japanese_banglish_retrieval_ndcg_and_acl(
    client: TestClient,
    db_session: Session,
):
    owner, owner_headers = _identity(client, "owner")
    intruder, intruder_headers = _identity(client, "intruder")
    examples = (
        (
            "english",
            "english.md",
            "The security audit rotation policy requires password review every 90 days.",
            "security audit rotation policy",
        ),
        (
            "bengali",
            "bengali.md",
            "তথ্যপ্রযুক্তি গবেষণায় তথ্য অনুসন্ধানের নির্ভুলতা গুরুত্বপূর্ণ।",
            "তথ্যপ্রযুক্তির গবেষণা",
        ),
        (
            "japanese",
            "japanese.md",
            "東京工芸大学情報システム研究室ではAIの検索技術を研究しています。",
            "東京工芸大学の研究室",
        ),
        (
            "banglish",
            "banglish.md",
            "Amader onboarding guide e salary policy niye proshno kora jay.",
            "onboarding guide salary policy",
        ),
    )
    document_ids = {
        key: _document(client, owner_headers, name, text)
        for key, name, text, _ in examples
    }
    private_doc = _document(
        client, intruder_headers, "different-user.md",
        "Private forbiddensecret9281 salary record must remain unavailable.",
    )

    cases = []
    rankings = {}
    for key, _, _, question in examples:
        relevant = frozenset(db_session.scalars(
            select(DocumentChunk.id).where(
                DocumentChunk.document_id == document_ids[key],
                DocumentChunk.chunk_role == "content",
            )
        ).all())
        assert relevant
        query = RetrievalQuery(
            user_id=owner,
            text=question,
            top_k=8,
        )
        hits = search_lexical_chunks(db_session, query)
        assert hits, f"{key} lost all lexical evidence"
        assert all(hit.document_id != private_doc for hit in hits)
        cases.append(RetrievalEvaluationCase(
            query_id=key,
            query=question,
            relevant_chunk_ids=relevant,
        ))
        rankings[key] = tuple(hit.chunk_id for hit in hits)

    metrics = evaluate_rankings(
        cases=tuple(cases),
        rankings=rankings,
        k=8,
    )
    assert metrics.case_count == 4
    assert metrics.hit_rate_at_k == 1.0
    assert metrics.mean_recall_at_k > 0
    assert metrics.mean_ndcg_at_k > 0
    assert metrics.mrr_at_k > 0
    assert all(0 <= case.ndcg_at_k <= 1 for case in metrics.cases)

    # Another tenant's searchable private phrase remains inaccessible even
    # if the client guesses the foreign document UUID.
    assert search_lexical_chunks(
        db_session,
        RetrievalQuery(
            user_id=owner,
            text="forbiddensecret9281",
            document_ids=(private_doc,),
            top_k=5,
        ),
    ) == []
