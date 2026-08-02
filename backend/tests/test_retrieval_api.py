from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import (
    DocumentChunk,
)


def create_user(
    client: TestClient,
    username: str,
    email: str,
) -> tuple[str, dict[str, str]]:
    password = "TestPass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()[
        "access_token"
    ]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    profile_response = client.get(
        "/api/v1/users/me",
        headers=headers,
    )

    assert profile_response.status_code == 200

    user_id = profile_response.json()["id"]

    return user_id, headers


def upload_and_process(
    client: TestClient,
    headers: dict[str, str],
    filename: str,
    content: str,
) -> str:
    upload_response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                content.encode("utf-8"),
                "text/markdown",
            ),
        },
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()[
        "id"
    ]

    process_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert process_response.status_code == 200

    return document_id


def get_document_chunk(
    db_session: Session,
    document_id: str,
    source_label: str | None = None,
) -> DocumentChunk:
    statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id
        )
        .order_by(
            DocumentChunk.chunk_index.asc()
        )
    )

    if source_label is not None:
        statement = statement.where(
            DocumentChunk.source_label
            == source_label
        )

    chunk = db_session.scalar(
        statement
    )

    assert chunk is not None

    return chunk


def test_retrieval_search_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/retrieval/search",
        json={
            "query": "How does retrieval work?",
        },
    )

    assert response.status_code == 401


def test_retrieval_api_returns_citation_ready_result(
    client: TestClient,
    db_session: Session,
) -> None:
    _, headers = create_user(
        client=client,
        username="apiuser",
        email="apiuser@example.com",
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="security.md",
        content=(
            "# Authentication\n\n"
            "JWT protects private API routes "
            "and validates authenticated users.\n\n"
            "# Retrieval\n\n"
            "Vector search retrieves relevant "
            "evidence with source citations."
        ),
    )

    target_chunk = get_document_chunk(
        db_session=db_session,
        document_id=document_id,
        source_label="Authentication",
    )

    response = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={
            "query": (
                target_chunk.embedding_content
            ),
            "top_k": 3,
            "document_ids": [
                document_id,
            ],
            "chunk_roles": [
                "content",
            ],
            "min_similarity": 0.999,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["query"] == (
        target_chunk.embedding_content
    )

    assert payload["total"] >= 1
    assert (
        payload["total"]
        == len(payload["items"])
    )

    first_item = payload["items"][0]

    assert (
        first_item["chunk_id"]
        == target_chunk.id
    )

    assert (
        first_item["document_id"]
        == document_id
    )

    assert (
        first_item["similarity_score"]
        >= 0.999
    )

    assert (
        first_item["source_label"]
        == "Authentication"
    )

    citation = first_item["citation"]

    assert (
        citation["filename"]
        == "security.md"
    )

    assert (
        citation["source_label"]
        == "Authentication"
    )

    assert citation["section_path"] == [
        "Authentication",
    ]

    assert citation["start_page"] is None
    assert citation["end_page"] is None


def test_retrieval_api_enforces_user_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    _, first_headers = create_user(
        client=client,
        username="firstapiuser",
        email="firstapi@example.com",
    )

    _, second_headers = create_user(
        client=client,
        username="secondapiuser",
        email="secondapi@example.com",
    )

    first_document_id = upload_and_process(
        client=client,
        headers=first_headers,
        filename="first-private.md",
        content=(
            "# First User\n\n"
            "This private evidence belongs "
            "only to the first user."
        ),
    )

    second_document_id = upload_and_process(
        client=client,
        headers=second_headers,
        filename="second-private.md",
        content=(
            "# Second User\n\n"
            "This private evidence belongs "
            "only to the second user."
        ),
    )

    second_chunk = get_document_chunk(
        db_session=db_session,
        document_id=second_document_id,
    )

    response = client.post(
        "/api/v1/retrieval/search",
        headers=first_headers,
        json={
            "query": (
                second_chunk.embedding_content
            ),
            "top_k": 10,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["items"]

    assert all(
        item["document_id"]
        == first_document_id
        for item in payload["items"]
    )

    assert all(
        item["document_id"]
        != second_document_id
        for item in payload["items"]
    )

    blocked_response = client.post(
        "/api/v1/retrieval/search",
        headers=first_headers,
        json={
            "query": (
                second_chunk.embedding_content
            ),
            "document_ids": [
                second_document_id,
            ],
        },
    )

    assert blocked_response.status_code == 200

    blocked_payload = (
        blocked_response.json()
    )

    assert blocked_payload["total"] == 0
    assert blocked_payload["items"] == []


def test_retrieval_request_validation(
    client: TestClient,
) -> None:
    _, headers = create_user(
        client=client,
        username="validationuser",
        email="validation@example.com",
    )

    empty_query_response = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={
            "query": "   ",
        },
    )

    assert (
        empty_query_response.status_code
        == 422
    )

    invalid_top_k_response = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={
            "query": "Valid search query",
            "top_k": 51,
        },
    )

    assert (
        invalid_top_k_response.status_code
        == 422
    )

    duplicate_filter_response = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={
            "query": "Valid search query",
            "document_ids": [
                "document-1",
                "document-1",
            ],
        },
    )

    assert (
        duplicate_filter_response.status_code
        == 422
    )
