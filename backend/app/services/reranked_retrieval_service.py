from dataclasses import replace

from sqlalchemy.orm import Session

from app.embeddings import EmbeddingProvider
from app.reranking import (
    RerankerError,
    RerankerProvider,
    RerankerScore,
)
from app.retrieval import (
    RetrievalHit,
    RetrievalQuery,
)
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)


DEFAULT_RERANK_CANDIDATE_DEPTH = 20


def _apply_reranker_scores(
    *,
    hits: list[RetrievalHit],
    scores: tuple[RerankerScore, ...],
    reranker: RerankerProvider,
) -> list[RetrievalHit]:
    hit_ids = {
        hit.chunk_id
        for hit in hits
    }

    score_by_id = {
        result.chunk_id: result.score
        for result in scores
    }

    if (
        len(scores) != len(hits)
        or set(score_by_id) != hit_ids
    ):
        raise RerankerError(
            "Reranker did not return exactly "
            "one score per candidate"
        )

    original_rank = {
        hit.chunk_id: index
        for index, hit in enumerate(
            hits,
            start=1,
        )
    }

    reranked = sorted(
        hits,
        key=lambda hit: (
            -score_by_id[hit.chunk_id],
            original_rank[hit.chunk_id],
        ),
    )

    output: list[RetrievalHit] = []

    for post_rank, hit in enumerate(
        reranked,
        start=1,
    ):
        reranker_score = (
            score_by_id[hit.chunk_id]
        )

        metadata = dict(
            hit.metadata
        )

        metadata.update(
            {
                "retrieval_mode": (
                    "hybrid_reranked"
                ),
                "pre_rerank_rank": (
                    original_rank[
                        hit.chunk_id
                    ]
                ),
                "post_rerank_rank": (
                    post_rank
                ),
                "pre_rerank_score": (
                    hit.ranking_score
                ),
                "reranker_score": (
                    reranker_score
                ),
                "reranker_provider": (
                    reranker
                    .info
                    .provider_name
                ),
                "reranker_model": (
                    reranker
                    .info
                    .model_name
                ),
            }
        )

        output.append(
            replace(
                hit,
                ranking_score=(
                    reranker_score
                ),
                metadata=metadata,
            )
        )

    return output


def rerank_hits(
    *,
    query_text: str,
    hits: list[RetrievalHit],
    reranker: RerankerProvider,
    fallback_on_error: bool = True,
) -> list[RetrievalHit]:
    if not hits:
        return []

    try:
        scores = reranker.rerank(
            query=query_text,
            hits=tuple(hits),
        )

        return _apply_reranker_scores(
            hits=hits,
            scores=scores,
            reranker=reranker,
        )

    except RerankerError:
        if not fallback_on_error:
            raise

        return list(hits)


def search_reranked_chunks(
    *,
    db: Session,
    query: RetrievalQuery,
    reranker: RerankerProvider,
    provider: EmbeddingProvider | None = None,
    candidate_depth: int = (
        DEFAULT_RERANK_CANDIDATE_DEPTH
    ),
    fallback_on_error: bool = True,
    reranker_query_text: str | None = None,
) -> list[RetrievalHit]:
    if not 1 <= candidate_depth <= 50:
        raise ValueError(
            "candidate_depth must be "
            "between 1 and 50"
        )

    if candidate_depth < query.top_k:
        raise ValueError(
            "candidate_depth cannot be "
            "smaller than query.top_k"
        )

    candidate_query = replace(
        query,
        top_k=candidate_depth,
    )

    hybrid_hits = search_hybrid_chunks(
        db=db,
        query=candidate_query,
        provider=provider,
    )

    reranked = rerank_hits(
        query_text=(
            reranker_query_text
            or query.text
        ),
        hits=hybrid_hits,
        reranker=reranker,
        fallback_on_error=(
            fallback_on_error
        ),
    )

    return reranked[
        :query.top_k
    ]
