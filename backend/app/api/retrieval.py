from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.logging import app_logger
from app.database.connection import get_db
from app.embeddings import EmbeddingError
from app.models.user import User
from app.retrieval import (
    RetrievalProviderError,
    RetrievalQuery,
    RetrievalValidationError,
)
from app.schemas.retrieval import (
    RetrievalCitationResponse,
    RetrievalItemResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.services.retrieval_service import (
    search_similar_chunks,
)


router = APIRouter(
    prefix="/retrieval",
    tags=["Retrieval"],
)


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
)
def search_documents(
    request: RetrievalSearchRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> RetrievalSearchResponse:
    try:
        hits = search_similar_chunks(
            db=db,
            query=RetrievalQuery(
                user_id=str(current_user.id),
                text=request.query,
                top_k=request.top_k,
                document_ids=(
                    request.document_ids
                ),
                chunk_roles=(
                    request.chunk_roles
                ),
                min_similarity=(
                    request.min_similarity
                ),
            ),
        )

    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc

    except RetrievalProviderError as exc:
        app_logger.exception(
            "Retrieval provider configuration "
            f"error: {exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Retrieval provider "
                "configuration failed"
            ),
        ) from exc

    except EmbeddingError as exc:
        app_logger.exception(
            "Query embedding failed: "
            f"{exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Query embedding service "
                "is unavailable"
            ),
        ) from exc

    items = [
        RetrievalItemResponse(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            parent_chunk_id=(
                hit.parent_chunk_id
            ),
            chunk_role=hit.chunk_role,
            chunk_level=hit.chunk_level,
            chunk_index=hit.chunk_index,
            source_label=hit.source_label,
            section_path=list(
                hit.section_path
            ),
            content=hit.content,
            similarity_score=(
                hit.similarity_score
            ),
            cosine_distance=(
                hit.cosine_distance
            ),
            citation=(
                RetrievalCitationResponse(
                    filename=(
                        hit.original_filename
                    ),
                    source_label=(
                        hit.source_label
                    ),
                    section_path=list(
                        hit.section_path
                    ),
                    start_page=hit.start_page,
                    end_page=hit.end_page,
                )
            ),
            metadata=dict(
                hit.metadata
            ),
        )
        for hit in hits
    ]

    app_logger.info(
        "Retrieval search completed: "
        f"user_id={current_user.id}, "
        f"results={len(items)}"
    )

    return RetrievalSearchResponse(
        query=request.query,
        total=len(items),
        items=items,
    )
