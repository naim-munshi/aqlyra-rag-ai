import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from app.models.document_chunk import (
    DocumentChunk,
)
from app.models.embedding_record import (
    EmbeddingRecord,
)
from app.retrieval import RetrievalQuery
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.retrieval_service import (
    score_specific_chunks,
    search_similar_chunks,
)


EXACT_TERM = "quasarvault917"


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


def get_content_chunks(
    db_session: Session,
    document_id: str,
) -> list[DocumentChunk]:
    statement = (
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

    return list(
        db_session.scalars(
            statement
        ).all()
    )


def get_term_chunk(
    db_session: Session,
    document_id: str,
) -> DocumentChunk:
    chunks = get_content_chunks(
        db_session=db_session,
        document_id=document_id,
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


def set_chunk_embedding(
    db_session: Session,
    chunk_id: str,
    vector: list[float],
) -> None:
    statement = (
        select(EmbeddingRecord)
        .where(
            EmbeddingRecord.chunk_id
            == chunk_id
        )
    )

    record = db_session.scalar(
        statement
    )

    assert record is not None

    record.embedding = vector


def test_db_hybrid_enriches_lexical_only_hit_and_isolates_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user_id, headers = create_user(
        client=client,
        username="hybriddbuser",
        email="hybriddb@example.com",
    )

    _, other_headers = create_user(
        client=client,
        username="hybriddbother",
        email="hybriddbother@example.com",
    )

    target_document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="target.md",
        content=(
            "# Private Vault\n\n"
            "The exact internal identifier "
            f"{EXACT_TERM} belongs to the "
            "primary private record."
        ),
    )

    other_document_id = upload_and_process(
        client=client,
        headers=other_headers,
        filename="other-private.md",
        content=(
            "# Other Private Vault\n\n"
            "Another user's private record "
            f"also contains {EXACT_TERM}."
        ),
    )

    distractor_document_ids: list[str] = []

    for number in range(4):
        document_id = upload_and_process(
            client=client,
            headers=headers,
            filename=(
                f"distractor-{number}.md"
            ),
            content=(
                f"# Distractor {number}\n\n"
                "This unrelated control record "
                f"contains ordinary text {number}."
            ),
        )

        distractor_document_ids.append(
            document_id
        )

    target_chunk = get_term_chunk(
        db_session=db_session,
        document_id=target_document_id,
    )

    other_chunk = get_term_chunk(
        db_session=db_session,
        document_id=other_document_id,
    )

    distractor_chunks = [
        get_content_chunks(
            db_session=db_session,
            document_id=document_id,
        )[0]
        for document_id
        in distractor_document_ids
    ]

    provider = (
        DeterministicHashEmbeddingProvider()
    )

    query_vector = provider.embed_query(
        EXACT_TERM
    )

    opposite_vector = [
        -value
        for value in query_vector
    ]

    # Force the four distractors to dominate
    # vector top-4 retrieval.
    for chunk in distractor_chunks:
        set_chunk_embedding(
            db_session=db_session,
            chunk_id=chunk.id,
            vector=list(query_vector),
        )

    # Keep the lexical target semantically last,
    # so it must enter hybrid retrieval through
    # the lexical channel and be enriched later.
    set_chunk_embedding(
        db_session=db_session,
        chunk_id=target_chunk.id,
        vector=opposite_vector,
    )

    # Give the other user's matching chunk a very
    # strong vector too. Tenant filters must still
    # prevent it from entering any result.
    set_chunk_embedding(
        db_session=db_session,
        chunk_id=other_chunk.id,
        vector=list(query_vector),
    )

    db_session.commit()

    retrieval_query = RetrievalQuery(
        user_id=user_id,
        text=EXACT_TERM,
        top_k=4,
        chunk_roles=("content",),
    )

    vector_results = search_similar_chunks(
        db=db_session,
        query=retrieval_query,
        provider=provider,
        query_vector=query_vector,
    )

    assert len(vector_results) == 4

    assert (
        target_chunk.id
        not in {
            result.chunk_id
            for result in vector_results
        }
    )

    assert all(
        result.document_id
        != other_document_id
        for result in vector_results
    )

    # Verify the enrichment query itself is
    # tenant-scoped even when another user's
    # chunk ID is explicitly supplied.
    enriched = score_specific_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=user_id,
            text=EXACT_TERM,
            top_k=1,
            chunk_roles=("content",),
        ),
        chunk_ids=(
            target_chunk.id,
            other_chunk.id,
        ),
        provider=provider,
        query_vector=query_vector,
    )

    assert set(enriched) == {
        target_chunk.id
    }

    assert (
        enriched[
            target_chunk.id
        ].similarity_score
        == pytest.approx(
            -1.0,
            abs=1e-5,
        )
    )

    assert (
        enriched[
            target_chunk.id
        ].cosine_distance
        == pytest.approx(
            2.0,
            abs=1e-5,
        )
    )

    # Lexical weight is intentionally higher here:
    # the target has lexical rank 1 but no vector
    # candidate rank.
    hybrid_results = search_hybrid_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=user_id,
            text=EXACT_TERM,
            top_k=1,
            chunk_roles=("content",),
        ),
        provider=provider,
        vector_weight=0.25,
        lexical_weight=1.0,
    )

    assert len(hybrid_results) == 1

    result = hybrid_results[0]

    assert result.chunk_id == target_chunk.id
    assert (
        result.document_id
        == target_document_id
    )

    assert (
        result.similarity_score
        == pytest.approx(
            -1.0,
            abs=1e-5,
        )
    )

    assert (
        result.cosine_distance
        == pytest.approx(
            2.0,
            abs=1e-5,
        )
    )

    assert result.ranking_score is not None
    assert result.ranking_score > 0.0

    assert (
        result.metadata["vector_rank"]
        is None
    )

    assert (
        result.metadata["lexical_rank"]
        == 1
    )

    assert (
        result.metadata[
            "retrieval_sources"
        ]
        == ["lexical"]
    )

    assert (
        result.metadata[
            "semantic_similarity_score"
        ]
        == pytest.approx(
            -1.0,
            abs=1e-5,
        )
    )

    assert (
        result.document_id
        != other_document_id
    )
