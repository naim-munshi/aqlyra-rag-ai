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
from app.schemas.embedding_indexing import (
    EmbeddingReindexResponse,
)
from app.services.document_service import (
    get_user_document,
)
from app.services.embedding_reindex_service import (
    DocumentChunksNotFoundError,
    DocumentNotReadyForEmbeddingError,
    reindex_document_embeddings,
)
from app.services.embedding_service import (
    EmbeddingBatchError,
    EmbeddingDimensionError,
)


router = APIRouter(
    prefix="/documents",
    tags=["Embeddings"],
)


@router.post(
    "/{document_id}/embeddings/rebuild",
    response_model=EmbeddingReindexResponse,
)
def rebuild_document_embeddings(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> EmbeddingReindexResponse:
    document = get_user_document(
        db=db,
        user_id=str(current_user.id),
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        result = reindex_document_embeddings(
            db=db,
            document=document,
        )

    except (
        DocumentNotReadyForEmbeddingError,
        DocumentChunksNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except EmbeddingError as exc:
        app_logger.exception(
            "Embedding provider failed during "
            f"document re-indexing: {exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Embedding provider is unavailable"
            ),
        ) from exc

    except (
        EmbeddingDimensionError,
        EmbeddingBatchError,
    ) as exc:
        app_logger.exception(
            "Embedding pipeline configuration "
            f"failed: {exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Embedding pipeline "
                "configuration failed"
            ),
        ) from exc

    app_logger.info(
        "Document embeddings rebuilt: "
        f"document_id={document_id}, "
        f"provider={result.provider_name}, "
        f"model={result.model_name}, "
        f"chunks={result.chunk_count}"
    )

    return EmbeddingReindexResponse(
        document_id=result.document_id,
        provider_name=result.provider_name,
        model_name=result.model_name,
        dimension=result.dimension,
        chunk_count=result.chunk_count,
        replaced_count=result.replaced_count,
        created_count=result.created_count,
    )
