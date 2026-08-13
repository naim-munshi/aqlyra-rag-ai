from dataclasses import replace

from sqlalchemy.orm import Session

from app.embeddings import EmbeddingProvider
from app.retrieval import (
    RetrievalHit,
    RetrievalQuery,
)
from app.retrieval.rank_fusion import (
    DEFAULT_RRF_K,
    reciprocal_rank_fusion,
)
from app.services.lexical_retrieval_service import (
    LexicalRetrievalHit,
    search_lexical_chunks,
)
from app.services.retrieval_service import (
    search_similar_chunks,
)


DEFAULT_CANDIDATE_MULTIPLIER = 4
MAX_CANDIDATES = 50


def _candidate_limit(
    top_k: int,
    multiplier: int,
) -> int:
    if multiplier < 1:
        raise ValueError(
            "candidate_multiplier must be at least 1"
        )

    return min(
        MAX_CANDIDATES,
        max(
            top_k,
            top_k * multiplier,
        ),
    )


def _normalized_rrf_score(
    *,
    score: float,
    rrf_k: int,
    vector_weight: float,
    lexical_weight: float,
) -> float:
    maximum_score = (
        vector_weight + lexical_weight
    ) / (rrf_k + 1)

    if maximum_score <= 0:
        return 0.0

    normalized = score / maximum_score

    return max(
        0.0,
        min(1.0, normalized),
    )


def _build_hybrid_hit(
    *,
    vector_hit: RetrievalHit | None,
    lexical_hit: LexicalRetrievalHit | None,
    hybrid_score: float,
    raw_rrf_score: float,
    vector_rank: int | None,
    lexical_rank: int | None,
) -> RetrievalHit:
    source = vector_hit or lexical_hit

    if source is None:
        raise ValueError(
            "Hybrid result requires at least "
            "one retrieval source"
        )

    metadata = dict(
        source.metadata
    )

    metadata.update(
        {
            "retrieval_mode": "hybrid",
            "hybrid_score": hybrid_score,
            "rrf_score": raw_rrf_score,
            "vector_rank": vector_rank,
            "lexical_rank": lexical_rank,
            "semantic_similarity_score": (
                vector_hit.similarity_score
                if vector_hit is not None
                else None
            ),
            "lexical_score": (
                lexical_hit.lexical_score
                if lexical_hit is not None
                else None
            ),
        }
    )

    # For hybrid RAG retrieval, similarity_score is the
    # normalized fused retrieval score. The original dense
    # similarity remains available in metadata.
    return RetrievalHit(
        chunk_id=source.chunk_id,
        document_id=source.document_id,
        original_filename=(
            source.original_filename
        ),
        parent_chunk_id=(
            source.parent_chunk_id
        ),
        chunk_role=source.chunk_role,
        chunk_level=source.chunk_level,
        chunk_index=source.chunk_index,
        source_label=source.source_label,
        section_path=source.section_path,
        content=source.content,
        start_page=source.start_page,
        end_page=source.end_page,
        similarity_score=hybrid_score,
        cosine_distance=(
            max(
                0.0,
                min(
                    2.0,
                    1.0 - hybrid_score,
                ),
            )
        ),
        metadata=metadata,
    )


def search_hybrid_chunks(
    db: Session,
    query: RetrievalQuery,
    provider: EmbeddingProvider | None = None,
    *,
    candidate_multiplier: int = (
        DEFAULT_CANDIDATE_MULTIPLIER
    ),
    rrf_k: int = DEFAULT_RRF_K,
    vector_weight: float = 1.0,
    lexical_weight: float = 1.0,
) -> list[RetrievalHit]:
    """
    Retrieve dense and lexical candidates and combine
    them with Reciprocal Rank Fusion.
    """

    candidate_k = _candidate_limit(
        query.top_k,
        candidate_multiplier,
    )

    candidate_query = replace(
        query,
        top_k=candidate_k,
    )

    vector_hits = search_similar_chunks(
        db=db,
        query=candidate_query,
        provider=provider,
    )

    lexical_hits = search_lexical_chunks(
        db=db,
        query=candidate_query,
    )

    vector_by_id = {
        hit.chunk_id: hit
        for hit in vector_hits
    }

    lexical_by_id = {
        hit.chunk_id: hit
        for hit in lexical_hits
    }

    fused_ranks = reciprocal_rank_fusion(
        vector_chunk_ids=tuple(
            hit.chunk_id
            for hit in vector_hits
        ),
        lexical_chunk_ids=tuple(
            hit.chunk_id
            for hit in lexical_hits
        ),
        rrf_k=rrf_k,
        vector_weight=vector_weight,
        lexical_weight=lexical_weight,
    )

    hybrid_hits: list[RetrievalHit] = []

    for fused in fused_ranks:
        vector_hit = vector_by_id.get(
            fused.chunk_id
        )

        lexical_hit = lexical_by_id.get(
            fused.chunk_id
        )

        # An explicit semantic threshold means the
        # result must have passed dense retrieval too.
        if (
            query.min_similarity is not None
            and vector_hit is None
        ):
            continue

        hybrid_score = _normalized_rrf_score(
            score=fused.score,
            rrf_k=rrf_k,
            vector_weight=vector_weight,
            lexical_weight=lexical_weight,
        )

        hybrid_hits.append(
            _build_hybrid_hit(
                vector_hit=vector_hit,
                lexical_hit=lexical_hit,
                hybrid_score=hybrid_score,
                raw_rrf_score=fused.score,
                vector_rank=fused.vector_rank,
                lexical_rank=(
                    fused.lexical_rank
                ),
            )
        )

        if len(hybrid_hits) >= query.top_k:
            break

    return hybrid_hits