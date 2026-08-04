from collections.abc import Sequence

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.services.embedding_reindex_service as reindex_module
from app.embeddings import (
    DeterministicHashEmbeddingProvider,
    EmbeddingProviderInfo,
)
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord


class ReindexTestProvider:
    def __init__(self) -> None:
        self._delegate = (
            DeterministicHashEmbeddingProvider(
                dimension=384,
                max_batch_size=64,
            )
        )

        self._info = EmbeddingProviderInfo(
            provider_name="reindex-test",
            model_name="reindex-test-v1",
            dimension=384,
            max_batch_size=64,
        )

    @property
    def info(self) -> EmbeddingProviderInfo:
        return self._info

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        return self._delegate.embed_documents(
            texts
        )

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self._delegate.embed_query(
            text
        )


def create_user(
    client: TestClient,
    *,
    username: str,
    email: str,
) -> dict[str, str]:
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

    return {
        "Authorization": f"Bearer {token}",
    }


def upload_document(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
) -> str:
    content = (
        "# Re-indexing\n\n"
        "Existing chunks can be embedded "
        "again without parsing the source "
        "document again.\n\n"
        "# Safety\n\n"
        "The replacement occurs within a "
        "database transaction."
    )

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

    return upload_response.json()["id"]


def process_document(
    client: TestClient,
    headers: dict[str, str],
    document_id: str,
) -> None:
    response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert response.status_code == 200


def count_provider_records(
    db_session: Session,
    *,
    document_id: str,
    provider_name: str,
    model_name: str,
) -> int:
    statement = (
        select(func.count())
        .select_from(EmbeddingRecord)
        .join(
            DocumentChunk,
            DocumentChunk.id
            == EmbeddingRecord.chunk_id,
        )
        .where(
            DocumentChunk.document_id
            == document_id,
            EmbeddingRecord.provider_name
            == provider_name,
            EmbeddingRecord.model_name
            == model_name,
        )
    )

    return (
        db_session.scalar(statement)
        or 0
    )


def test_rebuild_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        (
            "/api/v1/documents/"
            "document-1/embeddings/rebuild"
        )
    )

    assert response.status_code == 401


def test_rebuild_replaces_matching_provider_records(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    provider = ReindexTestProvider()

    monkeypatch.setattr(
        reindex_module,
        "create_configured_embedding_provider",
        lambda: provider,
    )

    headers = create_user(
        client,
        username="reindexuser",
        email="reindex@example.com",
    )

    document_id = upload_document(
        client=client,
        headers=headers,
        filename="reindex.md",
    )

    process_document(
        client=client,
        headers=headers,
        document_id=document_id,
    )

    first_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/embeddings/rebuild"
        ),
        headers=headers,
    )

    assert first_response.status_code == 200

    first_payload = first_response.json()

    assert (
        first_payload["provider_name"]
        == "reindex-test"
    )

    assert (
        first_payload["model_name"]
        == "reindex-test-v1"
    )

    assert first_payload["dimension"] == 384
    assert first_payload["chunk_count"] > 0
    assert first_payload["replaced_count"] == 0

    assert (
        first_payload["created_count"]
        == first_payload["chunk_count"]
    )

    first_record_count = count_provider_records(
        db_session,
        document_id=document_id,
        provider_name="reindex-test",
        model_name="reindex-test-v1",
    )

    assert first_record_count == (
        first_payload["chunk_count"]
    )

    second_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/embeddings/rebuild"
        ),
        headers=headers,
    )

    assert second_response.status_code == 200

    second_payload = second_response.json()

    assert (
        second_payload["replaced_count"]
        == first_record_count
    )

    assert (
        second_payload["created_count"]
        == first_record_count
    )

    second_record_count = count_provider_records(
        db_session,
        document_id=document_id,
        provider_name="reindex-test",
        model_name="reindex-test-v1",
    )

    assert second_record_count == (
        first_record_count
    )


def test_rebuild_rejects_unprocessed_document(
    client: TestClient,
    monkeypatch,
) -> None:
    provider = ReindexTestProvider()

    monkeypatch.setattr(
        reindex_module,
        "create_configured_embedding_provider",
        lambda: provider,
    )

    headers = create_user(
        client,
        username="unprocesseduser",
        email="unprocessed@example.com",
    )

    document_id = upload_document(
        client=client,
        headers=headers,
        filename="unprocessed.md",
    )

    response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/embeddings/rebuild"
        ),
        headers=headers,
    )

    assert response.status_code == 409

    assert response.json()["detail"] == (
        "Document must be ready before "
        "embeddings can be rebuilt"
    )


def test_rebuild_enforces_document_ownership(
    client: TestClient,
) -> None:
    owner_headers = create_user(
        client,
        username="reindexowner",
        email="reindexowner@example.com",
    )

    other_headers = create_user(
        client,
        username="reindexother",
        email="reindexother@example.com",
    )

    document_id = upload_document(
        client=client,
        headers=owner_headers,
        filename="private-reindex.md",
    )

    response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/embeddings/rebuild"
        ),
        headers=other_headers,
    )

    assert response.status_code == 404
