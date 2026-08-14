import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
)
from app.query_rewriting import QueryRewriter
from app.reranking import RerankerProvider
from app.retrieval import RetrievalQuery
from app.retrieval.benchmark import (
    DEFAULT_CHUNK_ROLES,
    RetrievalBenchmarkSpec,
    resolve_evaluation_cases,
)
from app.retrieval.evaluation import (
    RetrievalEvaluationSummary,
    evaluate_rankings,
)
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.reranked_retrieval_service import (
    rerank_hits,
)
from app.services.retrieval_service import (
    search_similar_chunks,
)


@dataclass(frozen=True, slots=True)
class MultiKResult:
    k: int
    vector: RetrievalEvaluationSummary
    hybrid: RetrievalEvaluationSummary
    reranked: RetrievalEvaluationSummary

    hybrid_hit_rate_delta: float
    rerank_hit_rate_delta: float

    hybrid_recall_delta: float
    rerank_recall_delta: float

    hybrid_mrr_delta: float
    rerank_mrr_delta: float


@dataclass(frozen=True, slots=True)
class RerankingBenchmarkReport:
    provider_name: str
    model_name: str
    benchmark_label: str

    reranker_provider_name: str
    reranker_model_name: str

    query_rewriter_provider_name: str | None
    query_rewriter_model_name: str | None

    retrieval_depth: int
    case_count: int
    results: tuple[MultiKResult, ...]


def run_reranking_benchmark_once(
    *,
    db: Session,
    user_id: str,
    specs: tuple[
        RetrievalBenchmarkSpec,
        ...,
    ],
    reranker: RerankerProvider,
    ks: tuple[int, ...] = (
        1,
        3,
        5,
    ),
    retrieval_depth: int = 15,
    provider: EmbeddingProvider | None = None,
    query_rewriter: QueryRewriter | None = None,
    chunk_roles: tuple[
        str,
        ...,
    ] = DEFAULT_CHUNK_ROLES,
    delay_seconds: float = 0.0,
) -> RerankingBenchmarkReport:
    if not 1 <= retrieval_depth <= 50:
        raise ValueError(
            "retrieval_depth must be "
            "between 1 and 50"
        )

    if delay_seconds < 0:
        raise ValueError(
            "delay_seconds cannot be negative"
        )

    normalized_ks = tuple(
        sorted(set(ks))
    )

    if not normalized_ks:
        raise ValueError(
            "At least one K is required"
        )

    for k in normalized_ks:
        if not 1 <= k <= retrieval_depth:
            raise ValueError(
                "Every K must be between "
                "1 and retrieval_depth"
            )

    active_provider = (
        provider
        or create_configured_embedding_provider()
    )

    cases = resolve_evaluation_cases(
        db=db,
        user_id=user_id,
        specs=specs,
        chunk_roles=chunk_roles,
    )

    vector_rankings: dict[
        str,
        tuple[str, ...],
    ] = {}

    hybrid_rankings: dict[
        str,
        tuple[str, ...],
    ] = {}

    reranked_rankings: dict[
        str,
        tuple[str, ...],
    ] = {}

    total_cases = len(cases)

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print(
            f"[{index}/{total_cases}] "
            f"{case.query_id}"
        )

        retrieval_text = case.query

        if query_rewriter is not None:
            retrieval_text = (
                query_rewriter.rewrite(
                    case.query
                )
            )

        query = RetrievalQuery(
            user_id=user_id,
            text=retrieval_text,
            top_k=retrieval_depth,
            chunk_roles=chunk_roles,
        )

        vector_hits = search_similar_chunks(
            db=db,
            query=query,
            provider=active_provider,
        )

        hybrid_hits = search_hybrid_chunks(
            db=db,
            query=query,
            provider=active_provider,
        )

        reranked_hits = rerank_hits(
            query_text=case.query,
            hits=hybrid_hits,
            reranker=reranker,
            fallback_on_error=False,
        )

        vector_rankings[
            case.query_id
        ] = tuple(
            hit.chunk_id
            for hit in vector_hits
        )

        hybrid_rankings[
            case.query_id
        ] = tuple(
            hit.chunk_id
            for hit in hybrid_hits
        )

        reranked_rankings[
            case.query_id
        ] = tuple(
            hit.chunk_id
            for hit in reranked_hits
        )

        if (
            delay_seconds > 0
            and index < total_cases
        ):
            time.sleep(delay_seconds)

    results: list[
        MultiKResult
    ] = []

    for k in normalized_ks:
        vector = evaluate_rankings(
            cases=cases,
            rankings=vector_rankings,
            k=k,
        )

        hybrid = evaluate_rankings(
            cases=cases,
            rankings=hybrid_rankings,
            k=k,
        )

        reranked = evaluate_rankings(
            cases=cases,
            rankings=reranked_rankings,
            k=k,
        )

        results.append(
            MultiKResult(
                k=k,
                vector=vector,
                hybrid=hybrid,
                reranked=reranked,
                hybrid_hit_rate_delta=(
                    hybrid.hit_rate_at_k
                    - vector.hit_rate_at_k
                ),
                rerank_hit_rate_delta=(
                    reranked.hit_rate_at_k
                    - hybrid.hit_rate_at_k
                ),
                hybrid_recall_delta=(
                    hybrid.mean_recall_at_k
                    - vector.mean_recall_at_k
                ),
                rerank_recall_delta=(
                    reranked.mean_recall_at_k
                    - hybrid.mean_recall_at_k
                ),
                hybrid_mrr_delta=(
                    hybrid.mrr_at_k
                    - vector.mrr_at_k
                ),
                rerank_mrr_delta=(
                    reranked.mrr_at_k
                    - hybrid.mrr_at_k
                ),
            )
        )

    provider_info = active_provider.info

    if (
        provider_info.provider_name
        == "deterministic"
    ):
        benchmark_label = (
            "candidate-generation plumbing uses "
            "non-semantic deterministic embeddings; "
            "LLM reranking is semantic"
        )
    else:
        benchmark_label = (
            "semantic retrieval and reranking benchmark"
        )

    return RerankingBenchmarkReport(
        provider_name=(
            provider_info.provider_name
        ),
        model_name=(
            provider_info.model_name
        ),
        benchmark_label=benchmark_label,
        reranker_provider_name=(
            reranker.info.provider_name
        ),
        reranker_model_name=(
            reranker.info.model_name
        ),
        query_rewriter_provider_name=(
            query_rewriter.info.provider_name
            if query_rewriter is not None
            else None
        ),
        query_rewriter_model_name=(
            query_rewriter.info.model_name
            if query_rewriter is not None
            else None
        ),
        retrieval_depth=retrieval_depth,
        case_count=len(cases),
        results=tuple(results),
    )
