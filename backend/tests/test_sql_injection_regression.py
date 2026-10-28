"""Non-destructive SQL injection regression against disposable PostgreSQL.

These inputs are never sent to production. We verify account lookups and
full-text retrieval treat attack-looking strings as data, and remain scoped.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.document import Document
from app.retrieval.types import RetrievalQuery
from app.services.lexical_retrieval_service import search_lexical_chunks
from app.services.user_service import get_user_by_email, get_user_by_username


def register(client: TestClient, label: str) -> tuple[str, dict[str, str]]:
    password = "SQLiRegressionPass123!"
    email = f"{label}@example.com"
    registered = client.post("/api/v1/auth/register", json={
        "username": label, "email": email, "password": password,
    })
    assert registered.status_code == 201
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert response.status_code == 200
    bearer = {"Authorization": "Bearer " + response.json()["access_token"]}
    own = client.get("/api/v1/users/me", headers=bearer)
    assert own.status_code == 200
    return own.json()["id"], bearer


def test_sql_meta_characters_cannot_bypass_account_lookup(
    client: TestClient, db_session: Session,
):
    owner_id, headers = register(client, "sqliowner")
    injected_email = "sqliowner@example.com' OR '1'='1"
    injected_username = "sqliowner' UNION SELECT * FROM users --"
    assert get_user_by_email(db_session, injected_email) is None
    assert get_user_by_username(db_session, injected_username) is None
    attempted = client.post("/api/v1/auth/login", json={
        "email": injected_email,
        "password": "SQLiRegressionPass123!",
    })
    assert attempted.status_code in (401, 422)
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    own = client.get("/api/v1/users/me", headers=headers)
    assert own.status_code == 200
    assert own.json()["id"] == owner_id


def test_postgresql_full_text_query_is_bound_and_tenant_scoped(
    client: TestClient, db_session: Session,
):
    owner_id, owner = register(client, "sqlauthor")
    other_id, other = register(client, "sqlother")
    doc_ids: dict[str, str] = {}
    for who, headers in (("owner", owner), ("other", other)):
        response = client.post("/api/v1/documents/upload", headers=headers,
            files={"file": (who + ".md",
                f"# {who} secret\n\nOnly the {who} can read this record.",
                "text/markdown")})
        assert response.status_code == 201
        doc_ids[who] = response.json()["id"]
        processed = client.post(
            f"/api/v1/documents/{doc_ids[who]}/process", headers=headers,
        )
        assert processed.status_code == 200

    for payload in (
        "' OR '1'='1",
        "'); DROP TABLE users; --",
        "test' UNION SELECT secret FROM documents --",
    ):
        query = RetrievalQuery(
            user_id=owner_id, text=payload, top_k=5,
            chunk_roles=("content", "summary"),
        )
        hits = search_lexical_chunks(db_session, query)
        assert all(hit.document_id == doc_ids["owner"] for hit in hits)
        assert all(hit.document_id != doc_ids["other"] for hit in hits)

    assert db_session.scalar(select(func.count()).select_from(User)) == 2
    assert db_session.scalar(select(func.count()).select_from(Document)) == 2
    assert client.get(
        f"/api/v1/documents/{doc_ids['other']}", headers=owner,
    ).status_code == 404
    assert client.get(
        f"/api/v1/documents/{doc_ids['other']}", headers=other,
    ).status_code == 200
    assert owner_id != other_id
