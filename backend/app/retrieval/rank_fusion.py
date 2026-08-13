from collections.abc import Sequence
from dataclasses import dataclass


DEFAULT_RRF_K = 60


@dataclass(frozen=True, slots=True)
class FusedRank:
    chunk_id: str
    score: float

    vector_rank: int | None = None
    lexical_rank: int | None = None


def _unique_ranked_ids(
    chunk_ids: Sequence[str],
) -> tuple[str, ...]:
    """
    Preserve the first occurrence of every chunk ID.

    Retrieval channels should already be unique, but
    rank fusion remains deterministic if duplicates
    are supplied accidentally.
    """

    unique: list[str] = []
    seen: set[str] = set()

    for chunk_id in chunk_ids:
        cleaned = str(chunk_id).strip()

        if not cleaned:
            continue

        if cleaned in seen:
            continue

        seen.add(cleaned)
        unique.append(cleaned)

    return tuple(unique)


def reciprocal_rank_fusion(
    *,
    vector_chunk_ids: Sequence[str],
    lexical_chunk_ids: Sequence[str],
    rrf_k: int = DEFAULT_RRF_K,
    vector_weight: float = 1.0,
    lexical_weight: float = 1.0,
) -> list[FusedRank]:
    """
    Fuse dense-vector and lexical rankings with RRF.

    RRF avoids directly mixing cosine similarity and
    PostgreSQL full-text scores because those scores
    live on different numerical scales.
    """

    if rrf_k < 1:
        raise ValueError(
            "rrf_k must be at least 1"
        )

    if vector_weight < 0:
        raise ValueError(
            "vector_weight cannot be negative"
        )

    if lexical_weight < 0:
        raise ValueError(
            "lexical_weight cannot be negative"
        )

    if (
        vector_weight == 0
        and lexical_weight == 0
    ):
        raise ValueError(
            "At least one retrieval weight "
            "must be greater than zero"
        )

    vector_ids = _unique_ranked_ids(
        vector_chunk_ids
    )

    lexical_ids = _unique_ranked_ids(
        lexical_chunk_ids
    )

    vector_ranks = {
        chunk_id: rank
        for rank, chunk_id in enumerate(
            vector_ids,
            start=1,
        )
    }

    lexical_ranks = {
        chunk_id: rank
        for rank, chunk_id in enumerate(
            lexical_ids,
            start=1,
        )
    }

    all_chunk_ids = (
        set(vector_ranks)
        | set(lexical_ranks)
    )

    fused: list[FusedRank] = []

    for chunk_id in all_chunk_ids:
        vector_rank = vector_ranks.get(
            chunk_id
        )

        lexical_rank = lexical_ranks.get(
            chunk_id
        )

        score = 0.0

        if vector_rank is not None:
            score += (
                vector_weight
                / (rrf_k + vector_rank)
            )

        if lexical_rank is not None:
            score += (
                lexical_weight
                / (rrf_k + lexical_rank)
            )

        fused.append(
            FusedRank(
                chunk_id=chunk_id,
                score=score,
                vector_rank=vector_rank,
                lexical_rank=lexical_rank,
            )
        )

    def sort_key(
        item: FusedRank,
    ) -> tuple[
        float,
        int,
        int,
        int,
        str,
    ]:
        best_rank = min(
            rank
            for rank in (
                item.vector_rank,
                item.lexical_rank,
            )
            if rank is not None
        )

        return (
            -item.score,
            best_rank,
            (
                item.vector_rank
                if item.vector_rank is not None
                else 10**9
            ),
            (
                item.lexical_rank
                if item.lexical_rank is not None
                else 10**9
            ),
            item.chunk_id,
        )

    return sorted(
        fused,
        key=sort_key,
    )