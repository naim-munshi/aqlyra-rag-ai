import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
    RetrievalEvaluationSummary,
    evaluate_rankings,
)
from app.query_rewriting import QueryRewriter
from app.reranking import RerankerProvider
from app.retrieval.types import RetrievalQuery
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.retrieval_service import (
    search_similar_chunks,
)
from app.services.reranked_retrieval_service import (
    rerank_hits,
)


DEFAULT_CHUNK_ROLES = (
    "content",
    "summary",
)


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkSpec:
    query_id: str
    query: str
    document_filename: str
    evidence_marker: str

    def __post_init__(self) -> None:
        values = {
            "query_id": self.query_id,
            "query": self.query,
            "document_filename": (
                self.document_filename
            ),
            "evidence_marker": (
                self.evidence_marker
            ),
        }

        for field_name, value in values.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} cannot be empty"
                )


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkReport:
    provider_name: str
    model_name: str
    benchmark_label: str
    k: int
    retrieval_depth: int
    case_count: int
    vector: RetrievalEvaluationSummary
    hybrid: RetrievalEvaluationSummary
    hit_rate_delta: float
    recall_delta: float
    mrr_delta: float
    reranked: RetrievalEvaluationSummary | None = None
    query_rewriter_provider_name: str | None = None
    query_rewriter_model_name: str | None = None
    reranker_provider_name: str | None = None
    reranker_model_name: str | None = None
    rerank_hit_rate_delta: float | None = None
    rerank_recall_delta: float | None = None
    rerank_mrr_delta: float | None = None


def load_benchmark_specs(
    path: Path,
) -> tuple[RetrievalBenchmarkSpec, ...]:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "Benchmark dataset must be "
            "a JSON object"
        )

    raw_cases = payload.get(
        "cases"
    )

    if not isinstance(raw_cases, list):
        raise ValueError(
            "Benchmark dataset must contain "
            "a cases array"
        )

    if not raw_cases:
        raise ValueError(
            "Benchmark dataset must contain "
            "at least one case"
        )

    specs: list[
        RetrievalBenchmarkSpec
    ] = []

    required_fields = (
        "query_id",
        "query",
        "document_filename",
        "evidence_marker",
    )

    for index, raw_case in enumerate(
        raw_cases,
        start=1,
    ):
        if not isinstance(
            raw_case,
            dict,
        ):
            raise ValueError(
                "Benchmark case "
                f"{index} must be an object"
            )

        values: dict[str, str] = {}

        for field_name in required_fields:
            value = raw_case.get(
                field_name
            )

            if not isinstance(
                value,
                str,
            ):
                raise ValueError(
                    "Benchmark case "
                    f"{index} field "
                    f"{field_name} "
                    "must be a string"
                )

            values[field_name] = value

        specs.append(
            RetrievalBenchmarkSpec(
                query_id=(
                    values["query_id"]
                ),
                query=values["query"],
                document_filename=(
                    values[
                        "document_filename"
                    ]
                ),
                evidence_marker=(
                    values[
                        "evidence_marker"
                    ]
                ),
            )
        )

    query_ids = [
        spec.query_id
        for spec in specs
    ]

    if len(query_ids) != len(
        set(query_ids)
    ):
        raise ValueError(
            "Benchmark query IDs "
            "must be unique"
        )

    return tuple(specs)


def resolve_evaluation_cases(
    *,
    db: Session,
    user_id: str,
    specs: tuple[
        RetrievalBenchmarkSpec,
        ...,
    ],
    chunk_roles: tuple[
        str,
        ...,
    ] = DEFAULT_CHUNK_ROLES,
) -> tuple[
    RetrievalEvaluationCase,
    ...,
]:
    if not user_id.strip():
        raise ValueError(
            "user_id cannot be empty"
        )

    if not specs:
        raise ValueError(
            "At least one benchmark spec "
            "is required"
        )

    resolved: list[
        RetrievalEvaluationCase
    ] = []

    for spec in specs:
        statement = (
            select(DocumentChunk)
            .join(
                Document,
                Document.id
                == DocumentChunk.document_id,
            )
            .where(
                Document.user_id
                == user_id,
                Document.status
                == "ready",
                Document.original_filename
                == spec.document_filename,
                DocumentChunk.chunk_role.in_(
                    chunk_roles
                ),
            )
            .order_by(
                DocumentChunk.chunk_index.asc(),
                DocumentChunk.id.asc(),
            )
        )

        chunks = list(
            db.scalars(
                statement
            ).all()
        )

        if not chunks:
            raise ValueError(
                "No ready benchmark document "
                "found for query "
                f"{spec.query_id}: "
                f"{spec.document_filename}"
            )

        marker = (
            spec.evidence_marker
            .strip()
            .casefold()
        )

        relevant_chunk_ids = frozenset(
            str(chunk.id)
            for chunk in chunks
            if (
                marker
                in chunk.content.casefold()
                or marker
                in (
                    chunk.embedding_content
                    .casefold()
                )
            )
        )

        if not relevant_chunk_ids:
            raise ValueError(
                "Evidence marker could not "
                "be resolved for query "
                f"{spec.query_id}: "
                f"{spec.evidence_marker}"
            )

        resolved.append(
            RetrievalEvaluationCase(
                query_id=spec.query_id,
                query=spec.query,
                relevant_chunk_ids=(
                    relevant_chunk_ids
                ),
            )
        )

    return tuple(resolved)


def run_retrieval_benchmark(
    *,
    db: Session,
    user_id: str,
    specs: tuple[
        RetrievalBenchmarkSpec,
        ...,
    ],
    k: int = 5,
    retrieval_depth: int = 20,
    provider: EmbeddingProvider | None = None,
    reranker: RerankerProvider | None = None,
    query_rewriter: QueryRewriter | None = None,
    chunk_roles: tuple[
        str,
        ...,
    ] = DEFAULT_CHUNK_ROLES,
) -> RetrievalBenchmarkReport:
    if not 1 <= k <= 50:
        raise ValueError(
            "k must be between 1 and 50"
        )

    if not 1 <= retrieval_depth <= 50:
        raise ValueError(
            "retrieval_depth must be "
            "between 1 and 50"
        )

    if k > retrieval_depth:
        raise ValueError(
            "k cannot exceed "
            "retrieval_depth"
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

    for case in cases:
        retrieval_text = case.query

        if query_rewriter is not None:
            retrieval_text = (
                query_rewriter.rewrite(
                    case.query
                )
            )

        retrieval_query = RetrievalQuery(
            user_id=user_id,
            text=retrieval_text,
            top_k=retrieval_depth,
            chunk_roles=chunk_roles,
        )

        vector_hits = search_similar_chunks(
            db=db,
            query=retrieval_query,
            provider=active_provider,
        )

        hybrid_hits = search_hybrid_chunks(
            db=db,
            query=retrieval_query,
            provider=active_provider,
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

        if reranker is not None:
            reranked_hits = rerank_hits(
                query_text=case.query,
                hits=hybrid_hits,
                reranker=reranker,
                fallback_on_error=False,
            )

            reranked_rankings[
                case.query_id
            ] = tuple(
                hit.chunk_id
                for hit in reranked_hits
            )

    vector_summary = evaluate_rankings(
        cases=cases,
        rankings=vector_rankings,
        k=k,
    )

    hybrid_summary = evaluate_rankings(
        cases=cases,
        rankings=hybrid_rankings,
        k=k,
    )

    reranked_summary = (
        evaluate_rankings(
            cases=cases,
            rankings=reranked_rankings,
            k=k,
        )
        if reranker is not None
        else None
    )

    provider_info = (
        active_provider.info
    )

    if (
        provider_info.provider_name
        == "deterministic"
    ):
        benchmark_label = (
            "plumbing-only: deterministic "
            "embeddings are not semantic"
        )
    else:
        benchmark_label = (
            "semantic retrieval benchmark"
        )

    return RetrievalBenchmarkReport(
        provider_name=(
            provider_info.provider_name
        ),
        model_name=(
            provider_info.model_name
        ),
        benchmark_label=benchmark_label,
        k=k,
        retrieval_depth=retrieval_depth,
        case_count=len(cases),
        vector=vector_summary,
        hybrid=hybrid_summary,
        hit_rate_delta=(
            hybrid_summary.hit_rate_at_k
            - vector_summary.hit_rate_at_k
        ),
        recall_delta=(
            hybrid_summary.mean_recall_at_k
            - vector_summary.mean_recall_at_k
        ),
        mrr_delta=(
            hybrid_summary.mrr_at_k
            - vector_summary.mrr_at_k
        ),
        reranked=reranked_summary,
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
        reranker_provider_name=(
            reranker.info.provider_name
            if reranker is not None
            else None
        ),
        reranker_model_name=(
            reranker.info.model_name
            if reranker is not None
            else None
        ),
        rerank_hit_rate_delta=(
            reranked_summary.hit_rate_at_k
            - hybrid_summary.hit_rate_at_k
            if reranked_summary is not None
            else None
        ),
        rerank_recall_delta=(
            reranked_summary.mean_recall_at_k
            - hybrid_summary.mean_recall_at_k
            if reranked_summary is not None
            else None
        ),
        rerank_mrr_delta=(
            reranked_summary.mrr_at_k
            - hybrid_summary.mrr_at_k
            if reranked_summary is not None
            else None
        ),
    )
