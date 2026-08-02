from collections.abc import Sequence

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.services.embedding_service as embedding_service_module
import app.services.retrieval_service as retrieval_service_module
from app.embeddings import (
    DeterministicHashEmbeddingProvider,
    EmbeddingProviderInfo,
)
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord


class ConfiguredTestProvider:
    def __init__(self) -> None:
        self._delegate = (
            DeterministicHashEmbeddingProvider(
                dimension=384,
                max_batch_size=64,
            )
        )

        self._info = EmbeddingProviderInfo(
            provider_name="configured-test",
            model_name="configured-test-v1",
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


def create_auth_headers(
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


def upload_and_process(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
) -> str:
    content = (
        "# Configured Embeddings\n\n"
        "The embedding pipeline selects its "
        "provider from application settings.\n\n"
        "# Retrieval\n\n"
        "The query pipeline must use the same "
        "provider and model as document indexing."
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


def test_processing_uses_configured_provider(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    provider = ConfiguredTestProvider()

    monkeypatch.setattr(
        embedding_service_module,
        "create_configured_embedding_provider",
        lambda: provider,
    )

    headers = create_auth_headers(
        client,
        username="configuredindexuser",
        email="configuredindex@example.com",
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="configured-index.md",
    )

    records = list(
        db_session.scalars(
            select(EmbeddingRecord)
            .join(DocumentChunk)
            .where(
                DocumentChunk.document_id
                == document_id
            )
        ).all()
    )

    assert records

    assert all(
        record.provider_name
        == "configured-test"
        for record in records
    )

    assert all(
        record.model_name
        == "configured-test-v1"
        for record in records
    )


def test_retrieval_uses_matching_configured_provider(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    provider = ConfiguredTestProvider()

    monkeypatch.setattr(
        embedding_service_module,
        "create_configured_embedding_provider",
        lambda: provider,
    )

    monkeypatch.setattr(
        retrieval_service_module,
        "create_configured_embedding_provider",
        lambda: provider,
    )

    headers = create_auth_headers(
        client,
        username="configuredsearchuser",
        email="configuredsearch@example.com",
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="configured-search.md",
    )

    target_chunk = db_session.scalar(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id,
            DocumentChunk.chunk_role
            == "content",
        )
        .order_by(
            DocumentChunk.chunk_index.asc()
        )
    )

    assert target_chunk is not None

    response = client.post(
        "/api/v1/retrieval/search",
        headers=headers,
        json={
            "query": (
                target_chunk.embedding_content
            ),
            "top_k": 1,
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

    assert payload["total"] == 1

    assert (
        payload["items"][0]["chunk_id"]
        == target_chunk.id
    )

    assert (
        payload["items"][0][
            "similarity_score"
        ]
        >= 0.999
    )
