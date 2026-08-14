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
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from app.services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation_for_user,
    list_conversations_for_user,
    update_conversation,
)


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


def _conversation_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Conversation not found",
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_endpoint(
    request: ConversationCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    return create_conversation(
        db=db,
        user_id=str(current_user.id),
        title=request.title,
        mode=request.mode,
    )


@router.get(
    "",
    response_model=list[ConversationResponse],
)
def list_conversations_endpoint(
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
) -> list[ConversationResponse]:
    return list_conversations_for_user(
        db=db,
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation_endpoint(
    conversation_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    conversation = get_conversation_for_user(
        db=db,
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise _conversation_not_found()

    return conversation


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def update_conversation_endpoint(
    conversation_id: str,
    request: ConversationUpdate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    conversation = get_conversation_for_user(
        db=db,
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise _conversation_not_found()

    return update_conversation(
        db=db,
        conversation=conversation,
        title=request.title,
        mode=request.mode,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation_endpoint(
    conversation_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> Response:
    conversation = get_conversation_for_user(
        db=db,
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise _conversation_not_found()

    delete_conversation(
        db=db,
        conversation=conversation,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
