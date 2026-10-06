import csv
import random
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import DeterministicHashEmbeddingProvider
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.retrieval import RetrievalQuery
from app.services.hybrid_retrieval_service import search_hybrid_chunks
from app.services.lexical_retrieval_service import search_lexical_chunks
from app.services.retrieval_service import search_similar_chunks


QUERY_TERMS = (
    "coverageq101",
    "coverageq202",
    "coverageq303",
    "coverageq404",
    "coverageq505",
    "coverageq606",
    "coverageq707",
    "coverageq808",
)

COVERAGE_LEVELS = (
    1.00,
    0.90,
    0.75,
    0.50,
    0.25,
    0.10,
    0.00,
)

MASK_SEEDS = tuple(range(10))
TOP_K = 5
RRF_K = 60


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
    headers = {"Authorization": f"Bearer {token}"}

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

    chunks = list(db_session.scalars(statement).all())
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


def union_rrf(
    *,
    dense_ids: list[str],
    lexical_ids: list[str],
    top_k: int,
    rrf_k: int,
) -> list[str]:
    scores: dict[str, float] = {}

    for rank, chunk_id in enumerate(dense_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (
            1.0 / (rrf_k + rank)
        )

    for rank, chunk_id in enumerate(lexical_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (
            1.0 / (rrf_k + rank)
        )

    ranked = sorted(
        scores,
        key=lambda chunk_id: (-scores[chunk_id], chunk_id),
    )

    return ranked[:top_k]


def test_embedding_coverage_quantitative_pilot(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_id, user_a_headers = create_user(
        client,
        "coverageexperimentprimary",
        "coverageexperimentprimary@example.com",
    )

    _, user_b_headers = create_user(
        client,
        "coverageexperimentother",
        "coverageexperimentother@example.com",
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
            filename=f"experiment-primary-{number}.md",
            content=(
                f"# Authorized Record {number}\n\n"
                f"The exact identifier {term} "
                "belongs to this authorized research record."
            ),
        )

        other_document_id = upload_and_process(
            client=client,
            headers=user_b_headers,
            filename=f"experiment-private-{number}.md",
            content=(
                f"# Private Record {number}\n\n"
                f"The exact identifier {term} "
                "also appears in another user's private record."
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

    # Make the controlled target embedding exactly equal
    # to the query embedding. This removes dense-ranking
    # noise from this infrastructure pilot.
    original_records: dict[str, tuple[str, str, int]] = {}

    for term, chunk in zip(
        QUERY_TERMS,
        primary_chunks,
    ):
        record = get_embedding_record(
            db_session,
            chunk.id,
        )

        record.embedding = provider.embed_query(term)
        record.provider_name = "deterministic"
        record.model_name = "deterministic-sha256-v1"
        record.dimension = 384

        original_records[chunk.id] = (
            record.provider_name,
            record.model_name,
            record.dimension,
        )

    db_session.commit()

    output_dir = (
        Path("research")
        / "experiments"
        / "results"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_path = (
        output_dir
        / "embedding_coverage_pilot_v0.1_raw.csv"
    )

    summary_path = (
        output_dir
        / "embedding_coverage_pilot_v0.1_summary.csv"
    )

    raw_rows: list[dict[str, object]] = []

    for seed in MASK_SEEDS:
        rng = random.Random(seed)

        for coverage in COVERAGE_LEVELS:
            covered_count = int(
                round(
                    len(primary_chunks) * coverage
                )
            )

            covered_ids = {
                chunk.id
                for chunk in rng.sample(
                    primary_chunks,
                    covered_count,
                )
            }

            for chunk in primary_chunks:
                record = get_embedding_record(
                    db_session,
                    chunk.id,
                )

                if chunk.id in covered_ids:
                    (
                        record.provider_name,
                        record.model_name,
                        record.dimension,
                    ) = original_records[chunk.id]
                else:
                    # Research-only mask: leave the vector itself
                    # untouched, but make it incompatible with the
                    # active provider so current retrieval excludes it.
                    record.provider_name = (
                        "research-masked"
                    )
                    record.model_name = (
                        "research-masked-v0"
                    )
                    record.dimension = 384

            db_session.commit()

            for term, primary_chunk, other_chunk in zip(
                QUERY_TERMS,
                primary_chunks,
                other_chunks,
            ):
                query = RetrievalQuery(
                    user_id=user_a_id,
                    text=term,
                    top_k=TOP_K,
                    chunk_roles=("content",),
                )

                lexical_results = (
                    search_lexical_chunks(
                        db=db_session,
                        query=query,
                    )
                )

                dense_results = (
                    search_similar_chunks(
                        db=db_session,
                        query=query,
                        provider=provider,
                    )
                )

                current_hybrid_results = (
                    search_hybrid_chunks(
                        db=db_session,
                        query=query,
                        provider=provider,
                        vector_weight=1.0,
                        lexical_weight=1.0,
                    )
                )

                lexical_ids = [
                    hit.chunk_id
                    for hit in lexical_results
                ]

                dense_ids = [
                    hit.chunk_id
                    for hit in dense_results
                ]

                current_hybrid_ids = [
                    hit.chunk_id
                    for hit in current_hybrid_results
                ]

                union_ids = union_rrf(
                    dense_ids=dense_ids,
                    lexical_ids=lexical_ids,
                    top_k=TOP_K,
                    rrf_k=RRF_K,
                )

                raw_rows.append(
                    {
                        "seed": seed,
                        "coverage": coverage,
                        "query_term": term,
                        "target_covered": (
                            primary_chunk.id
                            in covered_ids
                        ),
                        "lexical_hit": int(
                            primary_chunk.id
                            in lexical_ids
                        ),
                        "dense_hit": int(
                            primary_chunk.id
                            in dense_ids
                        ),
                        "current_hybrid_hit": int(
                            primary_chunk.id
                            in current_hybrid_ids
                        ),
                        "union_rrf_hit": int(
                            primary_chunk.id
                            in union_ids
                        ),
                        "unauthorized_lexical": int(
                            other_chunk.id
                            in lexical_ids
                        ),
                        "unauthorized_dense": int(
                            other_chunk.id
                            in dense_ids
                        ),
                        "unauthorized_current_hybrid": int(
                            other_chunk.id
                            in current_hybrid_ids
                        ),
                        "unauthorized_union_rrf": int(
                            other_chunk.id
                            in union_ids
                        ),
                    }
                )

    with raw_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(raw_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(raw_rows)

    summary_rows: list[dict[str, object]] = []

    for coverage in COVERAGE_LEVELS:
        rows = [
            row
            for row in raw_rows
            if row["coverage"] == coverage
        ]

        count = len(rows)

        summary_rows.append(
            {
                "coverage": coverage,
                "observations": count,
                "lexical_recall_at_5": (
                    sum(
                        int(row["lexical_hit"])
                        for row in rows
                    )
                    / count
                ),
                "dense_recall_at_5": (
                    sum(
                        int(row["dense_hit"])
                        for row in rows
                    )
                    / count
                ),
                "current_hybrid_recall_at_5": (
                    sum(
                        int(row["current_hybrid_hit"])
                        for row in rows
                    )
                    / count
                ),
                "union_rrf_recall_at_5": (
                    sum(
                        int(row["union_rrf_hit"])
                        for row in rows
                    )
                    / count
                ),
                "unauthorized_total": sum(
                    int(row["unauthorized_lexical"])
                    + int(row["unauthorized_dense"])
                    + int(row["unauthorized_current_hybrid"])
                    + int(row["unauthorized_union_rrf"])
                    for row in rows
                ),
            }
        )

    with summary_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(summary_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\n===== EMBEDDING COVERAGE PILOT =====")

    for row in summary_rows:
        print(
            f"coverage={row['coverage']:.2f} "
            f"lexical={row['lexical_recall_at_5']:.3f} "
            f"dense={row['dense_recall_at_5']:.3f} "
            f"hybrid={row['current_hybrid_recall_at_5']:.3f} "
            f"union_rrf={row['union_rrf_recall_at_5']:.3f} "
            f"unauthorized={row['unauthorized_total']}"
        )

    # Security invariant.
    assert all(
        row["unauthorized_total"] == 0
        for row in summary_rows
    )

    # Lexical index remains complete under every embedding mask.
    assert all(
        row["lexical_recall_at_5"] == 1.0
        for row in summary_rows
    )

    # Complete embedding coverage should reproduce the
    # controlled dense target and preserve current hybrid recall.
    full = next(
        row
        for row in summary_rows
        if row["coverage"] == 1.0
    )

    assert full["dense_recall_at_5"] == 1.0
    assert full["current_hybrid_recall_at_5"] == 1.0

    print("\nRaw results:")
    print(raw_path)

    print("Summary:")
    print(summary_path)

    print("===== PILOT COMPLETE =====")
