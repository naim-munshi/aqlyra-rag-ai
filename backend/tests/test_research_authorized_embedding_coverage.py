import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import DeterministicHashEmbeddingProvider
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.retrieval import RetrievalQuery
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.lexical_retrieval_service import (
    search_lexical_chunks,
)


QUERY_TERMS = (
    "authorizedcoverage101",
    "authorizedcoverage202",
    "authorizedcoverage303",
    "authorizedcoverage404",
    "authorizedcoverage505",
    "authorizedcoverage606",
    "authorizedcoverage707",
    "authorizedcoverage808",
)

COVERAGE_LEVELS = (
    1.00,
    0.75,
    0.50,
    0.25,
    0.00,
)


def create_user(
    client: TestClient,
    username: str,
    email: str,
) -> tuple[str, dict[str, str]]:
    password = "ResearchCoveragePass123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
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
    filename: str,
    content: str,
) -> str:
    response = client.post(
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

    assert response.status_code == 201

    document_id = response.json()["id"]

    response = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )

    assert response.status_code == 200

    return document_id


def get_content_chunk(
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

    assert chunks

    return chunks[0]


def get_embedding_record(
    db_session: Session,
    chunk_id: str,
) -> EmbeddingRecord:
    record = db_session.scalar(
        select(EmbeddingRecord).where(
            EmbeddingRecord.chunk_id == chunk_id
        )
    )

    assert record is not None

    return record


def test_authorized_retrieval_degrades_with_embedding_coverage(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_id, user_a_headers = create_user(
        client,
        "coverageprimary",
        "coverageprimary@example.com",
    )

    user_b_id, user_b_headers = create_user(
        client,
        "coverageother",
        "coverageother@example.com",
    )

    primary_chunks: list[DocumentChunk] = []
    other_chunks: list[DocumentChunk] = []

    for number, term in enumerate(
        QUERY_TERMS,
        start=1,
    ):
        primary_document_id = upload_and_process(
            client=client,
            headers=user_a_headers,
            filename=f"primary-{number}.md",
            content=(
                f"# Authorized Record {number}\n\n"
                f"The exact identifier {term} "
                "belongs to the authorized record."
            ),
        )

        other_document_id = upload_and_process(
            client=client,
            headers=user_b_headers,
            filename=f"other-{number}.md",
            content=(
                f"# Other User Record {number}\n\n"
                f"The exact identifier {term} "
                "also exists in another user's private record."
            ),
        )

        primary_chunks.append(
            get_content_chunk(
                db_session,
                primary_document_id,
            )
        )

        other_chunks.append(
            get_content_chunk(
                db_session,
                other_document_id,
            )
        )

    provider = DeterministicHashEmbeddingProvider()

    # Make each authorized target maximally similar to its own
    # exact query. This removes accidental dense-ranking noise
    # from the pilot.
    for term, chunk in zip(
        QUERY_TERMS,
        primary_chunks,
    ):
        record = get_embedding_record(
            db_session,
            chunk.id,
        )

        record.embedding = provider.embed_query(
            term
        )

    db_session.commit()

    results = []

    for coverage in COVERAGE_LEVELS:
        covered_count = int(
            round(
                len(primary_chunks)
                * coverage
            )
        )

        covered_ids = {
            chunk.id
            for chunk in primary_chunks[
                :covered_count
            ]
        }

        # Restore the authorized target embeddings to
        # either the active deterministic provider or an
        # incompatible provider that current retrieval
        # deliberately excludes.
        for chunk in primary_chunks:
            record = get_embedding_record(
                db_session,
                chunk.id,
            )

            if chunk.id in covered_ids:
                record.provider_name = (
                    "deterministic"
                )
                record.model_name = (
                    "deterministic-sha256-v1"
                )
                record.dimension = 384
            else:
                record.provider_name = (
                    "huggingface"
                )
                record.model_name = (
                    "ibm-granite/"
                    "granite-embedding-97m-"
                    "multilingual-r2"
                )
                record.dimension = 384

        db_session.commit()

        lexical_hits = 0
        hybrid_hits = 0
        unauthorized_hits = 0

        for term, primary_chunk, other_chunk in zip(
            QUERY_TERMS,
            primary_chunks,
            other_chunks,
        ):
            query = RetrievalQuery(
                user_id=user_a_id,
                text=term,
                top_k=1,
                chunk_roles=("content",),
            )

            lexical_results = (
                search_lexical_chunks(
                    db=db_session,
                    query=query,
                )
            )

            lexical_ids = {
                hit.chunk_id
                for hit in lexical_results
            }

            if primary_chunk.id in lexical_ids:
                lexical_hits += 1

            hybrid_results = search_hybrid_chunks(
                db=db_session,
                query=query,
                provider=provider,
                vector_weight=1.0,
                lexical_weight=1.0,
            )

            hybrid_ids = {
                hit.chunk_id
                for hit in hybrid_results
            }

            if primary_chunk.id in hybrid_ids:
                hybrid_hits += 1

            if other_chunk.id in lexical_ids:
                unauthorized_hits += 1

            if other_chunk.id in hybrid_ids:
                unauthorized_hits += 1

        lexical_recall = (
            lexical_hits
            / len(QUERY_TERMS)
        )

        hybrid_recall = (
            hybrid_hits
            / len(QUERY_TERMS)
        )

        retention = (
            hybrid_recall
            / lexical_recall
            if lexical_recall > 0
            else 0.0
        )

        results.append(
            {
                "coverage": coverage,
                "lexical_recall": lexical_recall,
                "hybrid_recall": hybrid_recall,
                "hybrid_retention": retention,
                "unauthorized_exposure": (
                    unauthorized_hits
                ),
            }
        )

    print("\n===== RESEARCH PILOT =====")

    for result in results:
        print(
            f"coverage={result['coverage']:.2f} "
            f"lexical={result['lexical_recall']:.3f} "
            f"hybrid={result['hybrid_recall']:.3f} "
            f"retention={result['hybrid_retention']:.3f} "
            f"unauthorized="
            f"{result['unauthorized_exposure']}"
        )

    # Security invariant: another user's exact matching
    # document must never enter either retrieval path.
    assert all(
        result["unauthorized_exposure"] == 0
        for result in results
    )

    # Lexical retrieval should remain complete because
    # the exact target is still present and authorized.
    assert all(
        result["lexical_recall"] == pytest.approx(1.0)
        for result in results
    )

    # With complete coverage, hybrid should retain the
    # authorized lexical targets.
    assert results[0]["hybrid_recall"] == pytest.approx(
        1.0
    )

    print("===== PILOT COMPLETE =====")
