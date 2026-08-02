from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import (
    DocumentChunk,
)


USER_DATA = {
    "username": "chunkuser",
    "email": "chunkuser@example.com",
    "password": "TestPass123!",
}


def create_auth_headers(
    client: TestClient,
) -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json=USER_DATA,
    )

    assert (
        register_response.status_code
        == 201
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_DATA[
                "email"
            ],
            "password": USER_DATA[
                "password"
            ],
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()[
        "access_token"
    ]

    return {
        "Authorization": (
            f"Bearer {token}"
        ),
    }


def upload_document(
    client: TestClient,
    headers: dict[str, str],
    content: str,
):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "chunk-test.md",
                content.encode("utf-8"),
                "text/markdown",
            ),
        },
    )


def process_document(
    client: TestClient,
    headers: dict[str, str],
    document_id: str,
):
    return client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )


def get_document_chunks(
    db_session: Session,
    document_id: str,
) -> list[DocumentChunk]:
    statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id
        )
        .order_by(
            DocumentChunk
            .chunk_index
            .asc()
        )
    )

    return list(
        db_session.scalars(
            statement
        ).all()
    )


def test_processing_persists_content_chunks(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = create_auth_headers(
        client
    )

    content = (
        "# Introduction\n\n"
        "Ihsan RAG AI processes "
        "documents securely.\n\n"
        "# Retrieval\n\n"
        "The system retrieves relevant "
        "evidence with citations."
    )

    upload_response = upload_document(
        client=client,
        headers=headers,
        content=content,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()[
        "id"
    ]

    process_response = process_document(
        client=client,
        headers=headers,
        document_id=document_id,
    )

    assert process_response.status_code == 200

    chunks = get_document_chunks(
        db_session=db_session,
        document_id=document_id,
    )

    assert len(chunks) >= 2

    assert all(
        chunk.chunk_role == "content"
        for chunk in chunks
    )

    assert all(
        chunk.document_id
        == document_id
        for chunk in chunks
    )

    assert all(
        chunk.document_unit_id
        is not None
        for chunk in chunks
    )

    assert all(
        chunk.embedding_content
        for chunk in chunks
    )

    assert all(
        chunk.content_hash
        for chunk in chunks
    )

    assert all(
        chunk.strategy_version
        == "iahc-x-v1"
        for chunk in chunks
    )

    combined_content = " ".join(
        chunk.content
        for chunk in chunks
    )

    assert (
        "processes documents securely"
        in combined_content
    )

    assert (
        "retrieves relevant evidence"
        in combined_content
    )


def test_long_unit_persists_parent_child_chunks(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = create_auth_headers(
        client
    )

    sentences = " ".join(
        (
            f"Sentence {number} explains "
            "retrieval augmented generation "
            "using verifiable evidence and "
            "accurate source citations."
        )
        for number in range(1, 101)
    )

    content = (
        "# Advanced Retrieval\n\n"
        f"{sentences}"
    )

    upload_response = upload_document(
        client=client,
        headers=headers,
        content=content,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()[
        "id"
    ]

    process_response = process_document(
        client=client,
        headers=headers,
        document_id=document_id,
    )

    assert process_response.status_code == 200

    chunks = get_document_chunks(
        db_session=db_session,
        document_id=document_id,
    )

    summary_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_role
        == "summary"
    ]

    content_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_role
        == "content"
    ]

    assert len(summary_chunks) == 1
    assert len(content_chunks) > 1

    parent_chunk = summary_chunks[0]

    assert parent_chunk.chunk_level == 1
    assert (
        parent_chunk.parent_chunk_id
        is None
    )

    assert all(
        chunk.parent_chunk_id
        == parent_chunk.id
        for chunk in content_chunks
    )

    assert all(
        chunk.chunk_level == 0
        for chunk in content_chunks
    )

    assert all(
        chunk.start_char is not None
        and chunk.end_char is not None
        for chunk in content_chunks
    )
