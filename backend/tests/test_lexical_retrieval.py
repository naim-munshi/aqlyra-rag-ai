from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.retrieval import RetrievalQuery
from app.services.lexical_retrieval_service import (
    search_lexical_chunks,
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

    document_id = upload_response.json()["id"]

    process_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert process_response.status_code == 200

    return document_id


def test_lexical_search_finds_exact_terms(
    client: TestClient,
    db_session: Session,
) -> None:
    user_id, headers = create_user(
        client=client,
        username="lexicaluser",
        email="lexical@example.com",
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="security-policy.md",
        content=(
            "# Security Policy\n\n"
            "Aqlyra performs the annual "
            "security review every October.\n\n"
            "# Backup Policy\n\n"
            "Database backups are verified "
            "every Friday."
        ),
    )

    results = search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=user_id,
            text="annual security October",
            top_k=5,
            document_ids=(
                document_id,
            ),
            chunk_roles=("content",),
        ),
    )

    assert results

    assert any(
        "October" in result.content
        for result in results
    )

    assert all(
        result.document_id == document_id
        for result in results
    )

    assert all(
        result.lexical_score > 0
        for result in results
    )


def test_lexical_search_enforces_user_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    first_user_id, first_headers = create_user(
        client=client,
        username="lexicalfirst",
        email="lexicalfirst@example.com",
    )

    _, second_headers = create_user(
        client=client,
        username="lexicalsecond",
        email="lexicalsecond@example.com",
    )

    first_document_id = upload_and_process(
        client=client,
        headers=first_headers,
        filename="first-private.md",
        content=(
            "# First Private Document\n\n"
            "The first user owns confidential "
            "alpha information."
        ),
    )

    second_document_id = upload_and_process(
        client=client,
        headers=second_headers,
        filename="second-private.md",
        content=(
            "# Second Private Document\n\n"
            "The secret keyword is "
            "quantumfalcon."
        ),
    )

    results = search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=first_user_id,
            text="quantumfalcon",
            top_k=10,
        ),
    )

    assert all(
        result.document_id
        != second_document_id
        for result in results
    )

    blocked_results = search_lexical_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=first_user_id,
            text="quantumfalcon",
            document_ids=(
                second_document_id,
            ),
        ),
    )

    assert blocked_results == []

    assert all(
        result.document_id
        == first_document_id
        for result in results
    )