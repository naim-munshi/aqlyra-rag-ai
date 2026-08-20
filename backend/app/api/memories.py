from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.memory import (
    MemoryCreate,
    MemoryKind,
    MemoryResponse,
    MemoryUpdate,
)
from app.services.memory_embedding_service import (
    index_memory_embeddings_best_effort,
)
from app.services.memory_service import (
    MemoryValidationError,
    create_memory,
    delete_memory,
    get_memory_for_user,
    list_memories_for_user,
    update_memory,
)


router = APIRouter(
    prefix="/memories",
    tags=["Memories"],
)


def _memory_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Memory not found",
    )


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_memory_endpoint(
    request: MemoryCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    try:
        memory = create_memory(
            db=db,
            user_id=str(current_user.id),
            kind=request.kind,
            content=request.content,
            importance=request.importance,
            confidence=request.confidence,
        )

        index_memory_embeddings_best_effort(
            db=db,
            user_id=str(current_user.id),
            memory_ids=[memory.id],
        )

        return MemoryResponse.model_validate(
            memory
        )

    except MemoryValidationError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[MemoryResponse],
)
def list_memories_endpoint(
    kind: MemoryKind | None = Query(
        default=None,
    ),
    is_active: bool | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> list[MemoryResponse]:
    memories = list_memories_for_user(
        db=db,
        user_id=str(current_user.id),
        kind=kind,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    return [
        MemoryResponse.model_validate(memory)
        for memory in memories
    ]


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
)
def get_memory_endpoint(
    memory_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    memory = get_memory_for_user(
        db=db,
        user_id=str(current_user.id),
        memory_id=memory_id,
    )

    if memory is None:
        raise _memory_not_found()

    return MemoryResponse.model_validate(
        memory
    )


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
)
def update_memory_endpoint(
    memory_id: str,
    request: MemoryUpdate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    memory = get_memory_for_user(
        db=db,
        user_id=str(current_user.id),
        memory_id=memory_id,
    )

    if memory is None:
        raise _memory_not_found()

    previous_content = memory.content

    try:
        updated_memory = update_memory(
            db=db,
            memory=memory,
            kind=request.kind,
            content=request.content,
            importance=request.importance,
            confidence=request.confidence,
            is_active=request.is_active,
        )

        if (
            request.content is not None
            and updated_memory.content
            != previous_content
        ):
            index_memory_embeddings_best_effort(
                db=db,
                user_id=str(current_user.id),
                memory_ids=[
                    updated_memory.id
                ],
            )

        return MemoryResponse.model_validate(
            updated_memory
        )

    except MemoryValidationError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_memory_endpoint(
    memory_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> Response:
    memory = get_memory_for_user(
        db=db,
        user_id=str(current_user.id),
        memory_id=memory_id,
    )

    if memory is None:
        raise _memory_not_found()

    delete_memory(
        db=db,
        memory=memory,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
