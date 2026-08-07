import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
    EmbeddingRecord,
)


USER_DATA = {
    "username": "embeddinguser",
    "email": "embeddinguser@example.com",
    "password": "TestPass123!",
}


def create_auth_headers(
    client: TestClient,
) -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json=USER_DATA,
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_DATA["email"],
            "password": USER_DATA["password"],
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
) -> str:
    content = (
        "# Embedding Pipeline\n\n"
        "Aqlyra RAG AI converts document chunks "
        "into vector representations.\n\n"
        "# Retrieval\n\n"
        "Vector similarity helps locate relevant "
        "evidence for cited answers."
    )

    upload_response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "embedding-test.md",
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


def test_embedding_records_table_exists(
    db_session: Session,
) -> None:
    assert (
        EmbeddingRecord.__tablename__
        == "embedding_records"
    )

    vector_type = (
        EmbeddingRecord
        .__table__
        .c
        .embedding
        .type
    )

    assert vector_type.dim == EMBEDDING_DIMENSION


def test_processing_persists_one_embedding_per_chunk(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = create_auth_headers(
        client
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
    )

    chunks = list(
        db_session.scalars(
            select(DocumentChunk).where(
                DocumentChunk.document_id
                == document_id
            )
        ).all()
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

    assert len(chunks) > 0
    assert len(records) == len(chunks)

    records_by_chunk = {
        record.chunk_id: record
        for record in records
    }

    for chunk in chunks:
        record = records_by_chunk[
            chunk.id
        ]

        assert (
            record.provider_name
            == "deterministic"
        )

        assert (
            record.model_name
            == "deterministic-sha256-v1"
        )

        assert (
            record.dimension
            == EMBEDDING_DIMENSION
        )

        assert (
            record.content_hash
            == chunk.content_hash
        )

        assert (
            record.input_token_count
            == chunk.token_count
        )

        assert (
            record.estimated_cost_usd
            == 0.0
        )


def test_persisted_embeddings_are_normalized(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = create_auth_headers(
        client
    )

    document_id = upload_and_process(
        client=client,
        headers=headers,
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

    for record in records:
        vector = list(
            record.embedding
        )

        magnitude = math.sqrt(
            sum(
                float(value)
                * float(value)
                for value in vector
            )
        )

        assert len(vector) == (
            EMBEDDING_DIMENSION
        )

        assert magnitude == pytest.approx(
            1.0,
            abs=1e-5,
        )
