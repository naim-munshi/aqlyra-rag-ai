from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
)
from app.core.logging import app_logger
from app.database.connection import get_db
from app.embeddings import EmbeddingError
from app.llms import (
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMValidationError,
)
from app.models.user import User
from app.rag import (
    CitationValidationError,
    GroundedAnswerError,
)
from app.retrieval import (
    RetrievalProviderError,
    RetrievalValidationError,
)
from app.schemas.rag import (
    RAGAnswerRequest,
    RAGAnswerResponse,
    RAGCitationResponse,
    RAGUsageResponse,
)
from app.services.rag_answer_service import (
    answer_question,
)


router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)


@router.post(
    "/answer",
    response_model=RAGAnswerResponse,
)
def create_grounded_answer(
    request: RAGAnswerRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> RAGAnswerResponse:
    try:
        result = answer_question(
            db=db,
            user_id=str(current_user.id),
            question=request.question,
            top_k=request.top_k,
            document_ids=tuple(
                request.document_ids
            ),
            chunk_roles=tuple(
                request.chunk_roles
            ),
            min_similarity=(
                request.min_similarity
            ),
            max_context_tokens=(
                request.max_context_tokens
            ),
            max_source_tokens=(
                request.max_source_tokens
            ),
            max_sources=(
                request.max_sources
            ),
        )

    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc

    except (
        RetrievalProviderError,
        LLMValidationError,
    ) as exc:
        app_logger.exception(
            "RAG provider configuration "
            f"failed: {exc}"
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "RAG provider configuration "
                "failed"
            ),
        ) from exc

    except (
        EmbeddingError,
        LLMProviderRequestError,
    ) as exc:
        app_logger.exception(
            "RAG provider request failed: "
            f"{exc}"
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "RAG provider service "
                "is unavailable"
            ),
        ) from exc

    except (
        LLMProviderResponseError,
        CitationValidationError,
        GroundedAnswerError,
    ) as exc:
        app_logger.exception(
            "Grounded answer validation "
            f"failed: {exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "The generated answer failed "
                "grounding validation"
            ),
        ) from exc

    citations = [
        RAGCitationResponse(
            source_id=source.source_id,
            chunk_id=source.chunk_id,
            document_id=(
                source.document_id
            ),
            parent_chunk_id=(
                source.parent_chunk_id
            ),
            filename=(
                source.original_filename
            ),
            chunk_role=source.chunk_role,
            chunk_level=(
                source.chunk_level
            ),
            chunk_index=(
                source.chunk_index
            ),
            source_label=(
                source.source_label
            ),
            section_path=list(
                source.section_path
            ),
            start_page=source.start_page,
            end_page=source.end_page,
            similarity_score=(
                source.similarity_score
            ),
            excerpt=source.content,
            was_truncated=(
                source.was_truncated
            ),
        )
        for source in result.citations
    ]

    app_logger.info(
        "Grounded RAG answer completed: "
        f"user_id={current_user.id}, "
        f"retrieved={result.retrieved_count}, "
        f"citations={result.citation_count}, "
        f"refusal={result.is_refusal}"
    )

    return RAGAnswerResponse(
        question=result.question,
        answer=result.answer_text,
        is_refusal=result.is_refusal,
        provider_name=(
            result.provider_name
        ),
        model_name=result.model_name,
        response_id=result.response_id,
        citations=citations,
        citation_count=(
            result.citation_count
        ),
        retrieved_count=(
            result.retrieved_count
        ),
        context_source_count=(
            result.context_source_count
        ),
        skipped_evidence_count=(
            result.skipped_evidence_count
        ),
        evidence_was_truncated=(
            result.evidence_was_truncated
        ),
        usage=RAGUsageResponse(
            input_tokens=(
                result.input_tokens
            ),
            output_tokens=(
                result.output_tokens
            ),
            total_tokens=(
                result.total_tokens
            ),
            evidence_tokens=(
                result.evidence_tokens
            ),
        ),
    )
