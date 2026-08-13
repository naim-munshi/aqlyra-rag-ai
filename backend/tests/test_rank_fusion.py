import pytest

from app.retrieval.rank_fusion import (
    reciprocal_rank_fusion,
)


def test_rrf_combines_vector_and_lexical_rankings(
) -> None:
    results = reciprocal_rank_fusion(
        vector_chunk_ids=(
            "chunk-a",
            "chunk-b",
            "chunk-c",
        ),
        lexical_chunk_ids=(
            "chunk-b",
            "chunk-d",
            "chunk-c",
        ),
    )

    assert results

    assert results[0].chunk_id == "chunk-b"

    result_ids = {
        result.chunk_id
        for result in results
    }

    assert result_ids == {
        "chunk-a",
        "chunk-b",
        "chunk-c",
        "chunk-d",
    }

    chunk_b = next(
        result
        for result in results
        if result.chunk_id == "chunk-b"
    )

    assert chunk_b.vector_rank == 2
    assert chunk_b.lexical_rank == 1

    chunk_d = next(
        result
        for result in results
        if result.chunk_id == "chunk-d"
    )

    assert chunk_d.vector_rank is None
    assert chunk_d.lexical_rank == 2


def test_rrf_removes_duplicate_chunk_ids(
) -> None:
    results = reciprocal_rank_fusion(
        vector_chunk_ids=(
            "chunk-a",
            "chunk-a",
            "chunk-b",
        ),
        lexical_chunk_ids=(
            "chunk-b",
            "chunk-b",
        ),
    )

    assert [
        result.chunk_id
        for result in results
    ].count("chunk-a") == 1

    assert [
        result.chunk_id
        for result in results
    ].count("chunk-b") == 1


def test_rrf_rejects_invalid_configuration(
) -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(
            vector_chunk_ids=("chunk-a",),
            lexical_chunk_ids=("chunk-b",),
            rrf_k=0,
        )

    with pytest.raises(ValueError):
        reciprocal_rank_fusion(
            vector_chunk_ids=("chunk-a",),
            lexical_chunk_ids=("chunk-b",),
            vector_weight=-1.0,
        )

    with pytest.raises(ValueError):
        reciprocal_rank_fusion(
            vector_chunk_ids=("chunk-a",),
            lexical_chunk_ids=("chunk-b",),
            vector_weight=0.0,
            lexical_weight=0.0,
        )