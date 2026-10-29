from fastapi import (
    APIRouter,
    Depends,
    Response,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
)
from app.core.rate_limit import (
    limit_voice_request,
)
from app.database.connection import get_db
from app.models.user import User
from app.schemas.voice import (
    VoiceSessionCreate,
    VoiceSessionResponse,
)
from app.services.voice_session_service import (
    VoiceConfigurationError,
    VoiceConversationModeError,
    VoiceConversationNotFoundError,
    VoiceDocumentValidationError,
    create_voice_session,
    voice_is_ready,
)


router = APIRouter(
    prefix="/voice",
    tags=["Voice"],
)


@router.get("/status")
def voice_status(
    response: Response,
    _current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Credential-free and private; readiness does not assert a live RTC call."""
    response.headers["Cache-Control"] = "private, no-store"
    available = voice_is_ready()
    return {
        "available": available,
        "detail": (
            "Voice calling is ready to connect."
            if available
            else "Voice calling is not available yet. "
                 "Please continue with text chat."
        ),
    }


@router.post(
    "/session",
    response_model=VoiceSessionResponse,
    dependencies=[
        Depends(limit_voice_request),
    ],
)
def create_voice_session_endpoint(
    request: VoiceSessionCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> VoiceSessionResponse:
    try:
        result = create_voice_session(
            db=db,
            user=current_user,
            mode=request.mode,
            conversation_id=(
                request.conversation_id
            ),
            title=request.title,
            document_ids=tuple(
                request.document_ids
            ),
        )

    except VoiceConfigurationError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except (
        VoiceConversationModeError,
        VoiceDocumentValidationError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc

    except VoiceConversationNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    return VoiceSessionResponse(
        server_url=result.server_url,
        participant_token=(
            result.participant_token
        ),
        room_name=result.room_name,
        conversation_id=(
            result.conversation_id
        ),
        mode=result.mode,
    )
