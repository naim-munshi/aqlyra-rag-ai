import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import (
    DocumentChunk,
)
from app.retrieval import (
    RetrievalQuery,
    RetrievalValidationError,
)
from app.services.retrieval_service import (
    search_similar_chunks,
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
            DocumentChunk.chunk_index.asc()
        )
    )

    return list(
        db_session.scalars(
            statement
        ).all()
    )


def test_empty_retrieval_query_is_rejected() -> None:
    with pytest.raises(
        RetrievalValidationError
    ):
        RetrievalQuery(
            user_id="user-1",
            text="   ",
        )


def test_exact_chunk_embedding_is_top_result(
    client: TestClient,
    db_session: Session,
) -> None:
    user_id, headers = create_user(
        client=client,
        username="retrievaluser",
        email="retrieval@example.com",
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="retrieval.md",
        content=(
            "# Authentication\n\n"
            "JWT protects private API routes.\n\n"
            "# Retrieval\n\n"
            "Vector search locates relevant "
            "document evidence."
        ),
    )

    chunks = get_document_chunks(
        db_session=db_session,
        document_id=document_id,
    )

    target_chunk = chunks[0]

    results = search_similar_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=user_id,
            text=(
                target_chunk
                .embedding_content
            ),
            top_k=3,
            chunk_roles=(
                target_chunk.chunk_role,
            ),
        ),
    )

    assert results
    assert (
        results[0].chunk_id
        == target_chunk.id
    )

    assert (
        results[0].document_id
        == document_id
    )

    assert (
        results[0].similarity_score
        == pytest.approx(
            1.0,
            abs=1e-5,
        )
    )


def test_retrieval_enforces_user_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    first_user_id, first_headers = (
        create_user(
            client=client,
            username="firstuser",
            email="first@example.com",
        )
    )

    _, second_headers = create_user(
        client=client,
        username="seconduser",
        email="second@example.com",
    )

    first_document_id = upload_and_process(
        client=client,
        headers=first_headers,
        filename="first.md",
        content=(
            "# Private First Document\n\n"
            "This evidence belongs only "
            "to the first user."
        ),
    )

    second_document_id = upload_and_process(
        client=client,
        headers=second_headers,
        filename="second.md",
        content=(
            "# Private Second Document\n\n"
            "This evidence belongs only "
            "to the second user."
        ),
    )

    second_chunks = get_document_chunks(
        db_session=db_session,
        document_id=second_document_id,
    )

    results = search_similar_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=first_user_id,
            text=(
                second_chunks[0]
                .embedding_content
            ),
            top_k=10,
        ),
    )

    assert results

    assert all(
        result.document_id
        == first_document_id
        for result in results
    )

    assert all(
        result.document_id
        != second_document_id
        for result in results
    )

    blocked_results = search_similar_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=first_user_id,
            text=(
                second_chunks[0]
                .embedding_content
            ),
            document_ids=(
                second_document_id,
            ),
        ),
    )

    assert blocked_results == []


def test_document_and_role_filters_are_applied(
    client: TestClient,
    db_session: Session,
) -> None:
    user_id, headers = create_user(
        client=client,
        username="filteruser",
        email="filter@example.com",
    )

    first_document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="first-filter.md",
        content=(
            "# First Section\n\n"
            "The first document contains "
            "database security evidence."
        ),
    )

    long_content = " ".join(
        (
            f"Sentence {number} explains "
            "vector retrieval with reliable "
            "citations and document evidence."
        )
        for number in range(1, 101)
    )

    second_document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="second-filter.md",
        content=(
            "# Advanced Retrieval\n\n"
            f"{long_content}"
        ),
    )

    second_chunks = get_document_chunks(
        db_session=db_session,
        document_id=second_document_id,
    )

    summary_chunk = next(
        chunk
        for chunk in second_chunks
        if chunk.chunk_role == "summary"
    )

    summary_results = search_similar_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=user_id,
            text=(
                summary_chunk
                .embedding_content
            ),
            top_k=1,
            document_ids=(
                second_document_id,
            ),
            chunk_roles=("summary",),
        ),
    )

    assert len(summary_results) == 1
    assert (
        summary_results[0].chunk_role
        == "summary"
    )

    assert (
        summary_results[0].document_id
        == second_document_id
    )

    first_document_results = (
        search_similar_chunks(
            db=db_session,
            query=RetrievalQuery(
                user_id=user_id,
                text=(
                    summary_chunk
                    .embedding_content
                ),
                top_k=10,
                document_ids=(
                    first_document_id,
                ),
                chunk_roles=("content",),
            ),
        )
    )

    assert first_document_results

    assert all(
        result.document_id
        == first_document_id
        for result in first_document_results
    )

    assert all(
        result.chunk_role == "content"
        for result in first_document_results
    )
