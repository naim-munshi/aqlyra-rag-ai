import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
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



def test_hybrid_keeps_real_lexical_only_document_without_vectors(
    client: TestClient,
    db_session: Session,
) -> None:
    """Reproduce production embedding-429 indexing -> lexical-only corpus.

    When worker later comes back online, RRF must keep existing matched
    chunks instead of dropping evidence because no EmbeddingRecord exists.
    """
    owner_id, owner_headers = create_user(
        client=client,
        username="hybridfallbackowner",
        email="hybridfallbackowner@example.com",
    )
    outsider_id, _ = create_user(
        client=client,
        username="hybridfallbackoutsider",
        email="hybridfallbackoutsider@example.com",
    )
    doc_id = upload_and_process(
        client=client,
        headers=owner_headers,
        filename="real-lexical-only.md",
        content=(
            "# Owner's internal knowledge\n\n"
            "The access-control record contains "
            f"the exact code {EXACT_TERM} and is private."
        ),
    )

    # Simulate indexing while the embedding worker returned HTTP 429:
    # the parsed document and chunks are durable, but no fake vectors.
    chunk_ids = tuple(
        db_session.scalars(
            select(DocumentChunk.id).where(DocumentChunk.document_id == doc_id)
        ).all()
    )
    assert chunk_ids
    db_session.execute(
        delete(EmbeddingRecord).where(EmbeddingRecord.chunk_id.in_(chunk_ids))
    )
    db_session.commit()

    query = RetrievalQuery(
        user_id=owner_id,
        text=EXACT_TERM,
        top_k=8,
        document_ids=(doc_id,),
    )
    hits = search_hybrid_chunks(
        db=db_session,
        query=query,
        provider=DeterministicHashEmbeddingProvider(),
    )
    assert hits, "Lexical matches must not disappear from live hybrid retrieval"
    assert all(hit.document_id == doc_id for hit in hits)
    assert any(EXACT_TERM in hit.content.casefold() for hit in hits)
    assert all(
        hit.metadata["retrieval_mode"] == "lexical_only"
        and hit.metadata["semantic_similarity_available"] is False
        and hit.metadata["semantic_similarity_score"] is None
        and hit.metadata["retrieval_sources"] == ["lexical"]
        for hit in hits
    )
    assert all(hit.ranking_score is not None for hit in hits)

    # ACL filters are evaluated inside PostgreSQL before retrieval ranking.
    assert search_hybrid_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=outsider_id,
            text=EXACT_TERM,
            top_k=8,
            document_ids=(doc_id,),
        ),
        provider=DeterministicHashEmbeddingProvider(),
    ) == []

    # A caller explicitly requesting real cosine evidence cannot be
    # downgraded to lexical or assigned a fictional 0.0 similarity.
    assert search_hybrid_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=owner_id,
            text=EXACT_TERM,
            top_k=8,
            document_ids=(doc_id,),
            min_similarity=0.3,
        ),
        provider=DeterministicHashEmbeddingProvider(),
    ) == []


def test_stale_content_hash_vectors_are_not_scored(
    client: TestClient,
    db_session: Session,
) -> None:
    """Changed chunk bytes must invalidate stale dense scores, not lexical evidence.

    Simulates an incomplete semantic reindex in isolated PostgreSQL: the
    already-saved vector still belongs to a previous chunk revision.
    """
    owner_id, headers = create_user(
        client=client,
        username="stalecoshash",
        email="stalecoshash@example.com",
    )
    document_id = upload_and_process(
        client=client,
        headers=headers,
        filename="stale-cosine.md",
        content=(
            "# Internal record\n\n"
            f"The verified owner code is {EXACT_TERM} "
            "and must remain available for lexical search."
        ),
    )
    target = get_term_chunk(
        db_session=db_session,
        document_id=document_id,
    )
    record = db_session.scalar(
        select(EmbeddingRecord).where(
            EmbeddingRecord.chunk_id == target.id
        )
    )
    assert record is not None
    valid_hash = record.content_hash
    assert valid_hash == target.content_hash

    # Preserve the embedding row while making its provenance stale.
    record.content_hash = "0" * 64
    assert record.content_hash != target.content_hash
    db_session.commit()
    provider = DeterministicHashEmbeddingProvider()
    query = RetrievalQuery(
        user_id=owner_id,
        text=EXACT_TERM,
        document_ids=(document_id,),
        chunk_roles=("content",),
        top_k=8,
    )
    dense = search_similar_chunks(db=db_session, query=query, provider=provider)
    assert target.id not in {hit.chunk_id for hit in dense}
    assert score_specific_chunks(
        db=db_session,
        query=query,
        chunk_ids=(target.id,),
        provider=provider,
    ) == {}

    # Existing real lexical evidence survives without an invented cosine score.
    hybrid = search_hybrid_chunks(db=db_session, query=query, provider=provider)
    matched = next(hit for hit in hybrid if hit.chunk_id == target.id)
    assert matched.metadata["retrieval_mode"] == "lexical_only"
    assert matched.metadata["semantic_similarity_available"] is False
    assert matched.metadata["semantic_similarity_score"] is None

    strict = search_hybrid_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id=owner_id,
            text=EXACT_TERM,
            document_ids=(document_id,),
            chunk_roles=("content",),
            top_k=8,
            min_similarity=0.5,
        ),
        provider=provider,
    )
    assert target.id not in {hit.chunk_id for hit in strict}

    # A legitimately reindexed current hash is eligible again.
    record.content_hash = valid_hash
    db_session.commit()
    assert target.id in score_specific_chunks(
        db=db_session,
        query=query,
        chunk_ids=(target.id,),
        provider=provider,
    )

