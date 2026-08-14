import logging
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.llms import (
    LLMProvider,
    create_configured_llm_provider,
)
from app.rag import (
    CitationValidationError,
    EvidenceContextConfig,
    EvidenceSource,
    build_evidence_context,
    validate_grounded_answer_draft,
)
from app.rag.answer_service import (
    generate_grounded_answer_draft,
    repair_grounded_answer_draft,
)
from app.query_rewriting import (
    QueryRewriter,
    QueryRewriteError,
    create_configured_query_rewriter,
)
from app.reranking import (
    RerankerError,
    RerankerProvider,
    create_configured_reranker,
)
from app.retrieval import (
    RetrievalHit,
    RetrievalQuery,
)
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.reranked_retrieval_service import (
    search_reranked_chunks,
)


logger = logging.getLogger(__name__)


def _rewrite_retrieval_query(
    *,
    query: RetrievalQuery,
    query_rewriter: QueryRewriter | None = None,
) -> RetrievalQuery:
    """
    Rewrite only the retrieval query.

    The original user question remains authoritative
    for reranking and grounded answer generation.
    """

    if not settings.RAG_QUERY_REWRITE_ENABLED:
        return query

    try:
        active_rewriter = (
            query_rewriter
            or create_configured_query_rewriter()
        )

        rewritten_text = active_rewriter.rewrite(
            query.text
        )

    except QueryRewriteError as exc:
        logger.warning(
            "query_rewrite_failed "
            "fallback=original_query "
            "error_type=%s",
            type(exc).__name__,
        )
        return query

    return replace(
        query,
        text=rewritten_text,
    )


def _retrieve_rag_hits(
    *,
    db: Session,
    query: RetrievalQuery,
    reranker: RerankerProvider | None = None,
    query_rewriter: QueryRewriter | None = None,
) -> list[RetrievalHit]:
    """
    Retrieve RAG evidence with optional semantic reranking.

    Reranking is feature-gated. Configuration/provider failures
    fall back to the existing hybrid retrieval path.
    """

    original_query_text = query.text

    retrieval_query = _rewrite_retrieval_query(
        query=query,
        query_rewriter=query_rewriter,
    )

    reranking_enabled = (
        settings.RAG_RERANKER_ENABLED
    )

    candidate_depth = (
        settings.RERANKER_CANDIDATE_DEPTH
    )

    if (
        not reranking_enabled
        or query.top_k > candidate_depth
    ):
        return search_hybrid_chunks(
            db=db,
            query=retrieval_query,
        )

    try:
        active_reranker = (
            reranker
            or create_configured_reranker()
        )

    except RerankerError as exc:
        logger.warning(
            "reranker_config_failed "
            "fallback=hybrid "
            "error_type=%s",
            type(exc).__name__,
        )
        return search_hybrid_chunks(
            db=db,
            query=retrieval_query,
        )

    return search_reranked_chunks(
        db=db,
        query=retrieval_query,
        reranker=active_reranker,
        candidate_depth=candidate_depth,
        fallback_on_error=True,
        reranker_query_text=(
            original_query_text
        ),
    )


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I could not find enough evidence in "
    "the available documents to answer "
    "this question."
)


@dataclass(frozen=True, slots=True)
class RAGAnswerResult:
    question: str
    answer_text: str

    is_refusal: bool

    provider_name: str
    model_name: str
    response_id: str | None

    citations: tuple[EvidenceSource, ...]
    citation_count: int

    retrieved_count: int
    context_source_count: int
    skipped_evidence_count: int
    evidence_was_truncated: bool

    evidence_tokens: int

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


def answer_question(
    *,
    db: Session,
    user_id: str,
    question: str,
    top_k: int = 8,
    document_ids: tuple[str, ...] = (),
    chunk_roles: tuple[str, ...] = (
        "content",
        "summary",
    ),
    min_similarity: float | None = None,
    max_context_tokens: int = 2_400,
    max_source_tokens: int = 700,
    max_sources: int = 8,
    provider: LLMProvider | None = None,
    reranker: RerankerProvider | None = None,
    query_rewriter: QueryRewriter | None = None,
) -> RAGAnswerResult:
    cleaned_question = question.strip()

    active_provider = (
        provider
        or create_configured_llm_provider()
    )

    hits = _retrieve_rag_hits(
        db=db,
        query=RetrievalQuery(
            user_id=user_id,
            text=cleaned_question,
            top_k=top_k,
            document_ids=document_ids,
            chunk_roles=chunk_roles,
            min_similarity=min_similarity,
        ),
        reranker=reranker,
        query_rewriter=query_rewriter,
    )

    evidence_context = build_evidence_context(
        hits=hits,
        config=EvidenceContextConfig(
            max_context_tokens=(
                max_context_tokens
            ),
            max_source_tokens=(
                max_source_tokens
            ),
            max_sources=max_sources,
            min_similarity=(
                min_similarity
                if min_similarity is not None
                else -1.0
            ),
            include_roles=chunk_roles,
        ),
    )

    if not evidence_context.has_evidence:
        return RAGAnswerResult(
            question=cleaned_question,
            answer_text=(
                INSUFFICIENT_EVIDENCE_MESSAGE
            ),
            is_refusal=True,
            provider_name=(
                active_provider
                .info
                .provider_name
            ),
            model_name=(
                active_provider
                .info
                .model_name
            ),
            response_id=None,
            citations=(),
            citation_count=0,
            retrieved_count=len(hits),
            context_source_count=0,
            skipped_evidence_count=(
                evidence_context
                .skipped_count
            ),
            evidence_was_truncated=(
                evidence_context
                .was_truncated
            ),
            evidence_tokens=0,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )

    draft = generate_grounded_answer_draft(
        question=cleaned_question,
        evidence_context=evidence_context,
        provider=active_provider,
    )

    try:
        validated = (
            validate_grounded_answer_draft(
                draft
            )
        )

    except CitationValidationError:
        draft = repair_grounded_answer_draft(
            draft=draft,
            evidence_context=evidence_context,
            provider=active_provider,
        )

        validated = (
            validate_grounded_answer_draft(
                draft
            )
        )

    if validated.is_refusal:
        answer_text = (
            INSUFFICIENT_EVIDENCE_MESSAGE
        )

        citations: tuple[
            EvidenceSource,
            ...,
        ] = ()

    else:
        answer_text = (
            validated.answer_text
        )

        citations = (
            validated.cited_sources
        )

    return RAGAnswerResult(
        question=cleaned_question,
        answer_text=answer_text,
        is_refusal=validated.is_refusal,
        provider_name=(
            validated.provider_name
        ),
        model_name=validated.model_name,
        response_id=draft.response_id,
        citations=citations,
        citation_count=(
            validated.citation_count
        ),
        retrieved_count=len(hits),
        context_source_count=len(
            evidence_context.sources
        ),
        skipped_evidence_count=(
            evidence_context.skipped_count
        ),
        evidence_was_truncated=(
            evidence_context.was_truncated
        ),
        evidence_tokens=(
            evidence_context
            .estimated_tokens
        ),
        input_tokens=draft.input_tokens,
        output_tokens=draft.output_tokens,
        total_tokens=draft.total_tokens,
    )