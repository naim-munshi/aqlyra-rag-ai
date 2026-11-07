from dataclasses import replace

from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
)
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
    score_specific_chunks,
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



def _build_lexical_only_hit(
    *,
    hit: LexicalRetrievalHit,
    hybrid_score: float,
    raw_rrf_score: float,
    lexical_rank: int,
) -> RetrievalHit:
    """Preserve real matched passages that have no 384-d vector yet.

    Knowledge indexing can mark a document ready with lexical-only chunks
    when the remote embedding service is unavailable. Previously hybrid
    RRF silently discarded those authorized chunks on a healthy query
    because score_specific_chunks requires an EmbeddingRecord. Do not
    fabricate a semantic score or bypass an explicit similarity threshold.
    """
    return RetrievalHit(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        original_filename=hit.original_filename,
        parent_chunk_id=hit.parent_chunk_id,
        chunk_role=hit.chunk_role,
        chunk_level=hit.chunk_level,
        chunk_index=hit.chunk_index,
        source_label=hit.source_label,
        section_path=hit.section_path,
        content=hit.content,
        start_page=hit.start_page,
        end_page=hit.end_page,
        # Placeholder values required by RetrievalHit's numeric contract,
        # explicitly marked as unavailable and never used to rank/filter.
        similarity_score=0.0,
        cosine_distance=1.0,
        ranking_score=hybrid_score,
        metadata={
            **hit.metadata,
            "retrieval_mode": "lexical_only",
            "semantic_similarity_available": False,
            "semantic_similarity_score": None,
            "lexical_score": hit.lexical_score,
            "rrf_score": raw_rrf_score,
            "hybrid_score": hybrid_score,
            "vector_rank": None,
            "lexical_rank": lexical_rank,
            "retrieval_sources": ["lexical"],
        },
    )


def _build_hybrid_hit(
    *,
    semantic_hit: RetrievalHit,
    lexical_hit: LexicalRetrievalHit | None,
    hybrid_score: float,
    raw_rrf_score: float,
    vector_rank: int | None,
    lexical_rank: int | None,
) -> RetrievalHit:
    metadata = dict(
        semantic_hit.metadata
    )

    retrieval_sources: list[str] = []

    if vector_rank is not None:
        retrieval_sources.append(
            "vector"
        )

    if lexical_rank is not None:
        retrieval_sources.append(
            "lexical"
        )

    metadata.update(
        {
            "retrieval_mode": "hybrid",
            "hybrid_score": hybrid_score,
            "rrf_score": raw_rrf_score,
            "vector_rank": vector_rank,
            "lexical_rank": lexical_rank,
            "semantic_similarity_score": (
                semantic_hit.similarity_score
            ),
            "lexical_score": (
                lexical_hit.lexical_score
                if lexical_hit is not None
                else None
            ),
            "retrieval_sources": (
                retrieval_sources
            ),
        }
    )

    return RetrievalHit(
        chunk_id=semantic_hit.chunk_id,
        document_id=semantic_hit.document_id,
        original_filename=(
            semantic_hit.original_filename
        ),
        parent_chunk_id=(
            semantic_hit.parent_chunk_id
        ),
        chunk_role=semantic_hit.chunk_role,
        chunk_level=semantic_hit.chunk_level,
        chunk_index=semantic_hit.chunk_index,
        source_label=semantic_hit.source_label,
        section_path=semantic_hit.section_path,
        content=semantic_hit.content,
        start_page=semantic_hit.start_page,
        end_page=semantic_hit.end_page,

        # These retain their true dense-vector meaning.
        similarity_score=(
            semantic_hit.similarity_score
        ),
        cosine_distance=(
            semantic_hit.cosine_distance
        ),

        # This controls hybrid ranking.
        ranking_score=hybrid_score,

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
    Retrieve dense and lexical candidates, enrich
    lexical-only candidates with true dense scores,
    and combine rankings with Reciprocal Rank Fusion.
    """

    candidate_k = _candidate_limit(
        query.top_k,
        candidate_multiplier,
    )

    candidate_query = replace(
        query,
        top_k=candidate_k,
    )

    active_provider = (
        provider
        or create_configured_embedding_provider()
    )

    # Generate the query embedding exactly once.
    active_query_vector = (
        active_provider.embed_query(
            query.text
        )
    )

    vector_hits = search_similar_chunks(
        db=db,
        query=candidate_query,
        provider=active_provider,
        query_vector=active_query_vector,
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

    lexical_only_ids = tuple(
        hit.chunk_id
        for hit in lexical_hits
        if hit.chunk_id
        not in vector_by_id
    )

    enriched_hits = score_specific_chunks(
        db=db,
        query=candidate_query,
        chunk_ids=lexical_only_ids,
        provider=active_provider,
        query_vector=active_query_vector,
    )

    semantic_by_id = dict(
        vector_by_id
    )

    semantic_by_id.update(
        enriched_hits
    )

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
        semantic_hit = semantic_by_id.get(
            fused.chunk_id
        )

        lexical_hit = lexical_by_id.get(fused.chunk_id)

        hybrid_score = _normalized_rrf_score(
            score=fused.score,
            rrf_k=rrf_k,
            vector_weight=vector_weight,
            lexical_weight=lexical_weight,
        )

        if semantic_hit is None:
            # A real lexical match with no EmbeddingRecord is still valid
            # grounded evidence. However, callers demanding min_similarity
            # must not be silently downgraded from semantic verification.
            if (
                lexical_hit is None
                or fused.lexical_rank is None
                or query.min_similarity is not None
            ):
                continue
            hybrid_hits.append(
                _build_lexical_only_hit(
                    hit=lexical_hit,
                    hybrid_score=hybrid_score,
                    raw_rrf_score=fused.score,
                    lexical_rank=fused.lexical_rank,
                )
            )
        else:
            if (
                query.min_similarity is not None
                and semantic_hit.similarity_score < query.min_similarity
            ):
                continue
            hybrid_hits.append(
                _build_hybrid_hit(
                    semantic_hit=semantic_hit,
                    lexical_hit=lexical_hit,
                    hybrid_score=hybrid_score,
                    raw_rrf_score=fused.score,
                    vector_rank=fused.vector_rank,
                    lexical_rank=fused.lexical_rank,
                )
            )

        if len(hybrid_hits) >= query.top_k:
            break

    return hybrid_hits
