"""Regression: semantic 429 must not make ordinary Knowledge questions miss evidence.

This test uses the current PostgreSQL retrieval path and synthetic documents.
The incident's actual HTTP 429 was verified in Render logs. These offline
tests do not claim semantic provider availability, live users or real Groq
response quality.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.retrieval import RetrievalQuery
from app.services.lexical_retrieval_service import (
    _extract_query_terms,
    search_lexical_chunks,
)
def create_user(client: TestClient, username: str, email: str):
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "SyntheticTestPass123!",
        },
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SyntheticTestPass123!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile = client.get("/api/v1/users/me", headers=headers)
    assert profile.status_code == 200
    return profile.json()["id"], headers


def upload_and_process(
    client: TestClient, headers: dict[str, str],
    filename: str, content: str,
):
    uploaded = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    processed = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )
    assert processed.status_code == 200
    return document_id


def test_english_possessive_and_question_fillers_do_not_dominate_fts():
    assert _extract_query_terms(
        "What are Pilot Orion's support hours?"
    ) == ("Pilot", "Orion", "support", "hours")
    assert _extract_query_terms(
        "What are Pilot Orion’s support hours?"
    ) == ("Pilot", "Orion", "support", "hours")
    assert _extract_query_terms(
        "How many personal leave days are available?"
    ) == ("many", "personal", "leave", "days", "available")
    assert _extract_query_terms("what are") == ("what", "are")


def test_multilingual_query_content_remains_searchable():
    assert _extract_query_terms("HM-72 は何分ごとに測定しますか？") == (
        "HM-72", "は何分ごとに測定しますか？",
    )
    assert _extract_query_terms("রিফান্ড পেতে কত কর্মদিবস লাগে?") == (
        "রিফান্ড", "পেতে", "কত", "কর্মদিবস", "লাগে",
    )
    assert _extract_query_terms("Atlas er backup kobe hoy?") == (
        "Atlas", "er", "backup", "kobe", "hoy",
    )


def test_pg_lexical_pilot_orion_ignores_question_filler_chunks(
    client: TestClient,
    db_session: Session,
):
    owner_id, headers = create_user(
        client=client,
        username="orionlexicalowner",
        email="orionlexicalowner@example.com",
    )
    main_doc = upload_and_process(
        client=client,
        headers=headers,
        filename="02_Orion_Operations_Update.md",
        content=(
            "# Pilot Orion\n\nPilot Orion's support window is "
            "08:30–17:30 JST from Monday to Friday."
        ),
    )
    distractor = upload_and_process(
        client=client,
        headers=headers,
        filename="unrelated-faq.md",
        content=(
            "# FAQ\n\nWhat are the choices? "
            "What are these questions? "
            "The employee guide describes company contacts."
        ),
    )

    hits = search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=owner_id,
            text="What are Pilot Orion's support hours?",
            top_k=5,
            document_ids=(main_doc, distractor),
            chunk_roles=("content",),
        ),
    )
    assert hits
    assert hits[0].document_id == main_doc
    assert "08:30" in hits[0].content
    assert all(hit.document_id != distractor for hit in hits)


def test_pg_lexical_orion_remains_private_across_accounts(
    client: TestClient,
    db_session: Session,
):
    owner_id, owner_headers = create_user(
        client=client,
        username="orionownerprivate",
        email="orionownerprivate@example.com",
    )
    other_id, _ = create_user(
        client=client,
        username="orionotherprivate",
        email="orionotherprivate@example.com",
    )
    private_doc = upload_and_process(
        client=client,
        headers=owner_headers,
        filename="private-orion.md",
        content="# Private\n\nPilot Orion support 08:30–17:30 JST.",
    )
    assert search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=other_id,
            text="What are Pilot Orion's support hours?",
            top_k=5,
            document_ids=(private_doc,),
        ),
    ) == []
    assert search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=owner_id,
            text="What are Pilot Orion's support hours?",
            top_k=5,
            document_ids=(private_doc,),
        ),
    )
