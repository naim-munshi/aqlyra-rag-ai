import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.retrieval import RetrievalQuery
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.lexical_retrieval_service import (
    search_lexical_chunks,
)


EXACT_TERM = "researchcoverage817"


def create_user(
    client: TestClient,
) -> tuple[str, dict[str, str]]:
    password = "ResearchTestPass123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "researchcoverageuser",
            "email": "researchcoverage@example.com",
            "password": password,
        },
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "researchcoverage@example.com",
            "password": password,
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = client.get(
        "/api/v1/users/me",
        headers=headers,
    )

    assert response.status_code == 200

    return response.json()["id"], headers


def upload_and_process(
    client: TestClient,
    headers: dict[str, str],
) -> str:
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "coverage-target.md",
                (
                    "# Research Coverage\n\n"
                    "The exact identifier "
                    f"{EXACT_TERM} belongs to "
                    "this authorized research record."
                ).encode("utf-8"),
                "text/markdown",
            ),
        },
    )

    assert response.status_code == 201

    document_id = response.json()["id"]

    response = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )

    assert response.status_code == 200

    return document_id


def get_target_chunk(
    db_session: Session,
    document_id: str,
) -> DocumentChunk:
    statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.chunk_role == "content",
        )
        .order_by(DocumentChunk.chunk_index.asc())
    )

    chunks = list(
        db_session.scalars(statement).all()
    )

    target = next(
        (
            chunk
            for chunk in chunks
            if EXACT_TERM
            in chunk.embedding_content.lower()
        ),
        None,
    )

    assert target is not None

    return target


def test_hybrid_drops_lexical_hit_without_compatible_embedding(
    client: TestClient,
    db_session: Session,
) -> None:
    user_id, headers = create_user(client)

    document_id = upload_and_process(
        client=client,
        headers=headers,
    )

    chunk = get_target_chunk(
        db_session=db_session,
        document_id=document_id,
    )

    record = db_session.scalar(
        select(EmbeddingRecord).where(
            EmbeddingRecord.chunk_id == chunk.id
        )
    )

    assert record is not None

    # Simulate a historical/index-provenance mismatch:
    # the chunk still exists and remains lexically searchable,
    # but there is no embedding compatible with the active
    # deterministic provider.
    record.provider_name = "huggingface"
    record.model_name = (
        "ibm-granite/"
        "granite-embedding-97m-multilingual-r2"
    )
    record.dimension = 384

    db_session.commit()

    provider = (
        DeterministicHashEmbeddingProvider()
    )

    query = RetrievalQuery(
        user_id=user_id,
        text=EXACT_TERM,
        top_k=1,
        chunk_roles=("content",),
    )

    lexical_results = search_lexical_chunks(
        db=db_session,
        query=query,
    )

    lexical_ids = {
        result.chunk_id
        for result in lexical_results
    }

    assert chunk.id in lexical_ids

    # Active semantic provider has no compatible
    # embedding for this chunk.
    vector_results = (
        search_hybrid_chunks(
            db=db_session,
            query=query,
            provider=provider,
        )
    )

    hybrid_ids = {
        result.chunk_id
        for result in vector_results
    }

    assert chunk.id not in hybrid_ids

    print(
        "\nResearch pilot:"
        "\n  lexical_hit = True"
        "\n  hybrid_hit  = False"
        "\n  compatible_embedding = False"
    )
