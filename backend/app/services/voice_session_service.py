import json
from dataclasses import dataclass
from uuid import uuid4

from livekit import api
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.conversation import (
    ConversationMode,
)
from app.services.conversation_service import (
    create_conversation,
    get_conversation_for_user,
)
from app.services.document_service import (
    get_user_document,
)


class VoiceConfigurationError(
    RuntimeError
):
    pass


class VoiceConversationNotFoundError(
    ValueError
):
    pass


class VoiceConversationModeError(
    ValueError
):
    pass


class VoiceDocumentValidationError(
    ValueError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class VoiceSessionResult:
    server_url: str
    participant_token: str
    room_name: str

    conversation_id: str
    mode: ConversationMode


def _require_voice_configuration() -> None:
    missing = [
        name
        for name, value in (
            (
                "LIVEKIT_URL",
                settings.LIVEKIT_URL,
            ),
            (
                "LIVEKIT_API_KEY",
                settings.LIVEKIT_API_KEY,
            ),
            (
                "LIVEKIT_API_SECRET",
                settings.LIVEKIT_API_SECRET,
            ),
        )
        if not value.strip()
    ]

    if missing:
        raise VoiceConfigurationError(
            "Voice service is not configured"
        )

    if not settings.VOICE_AGENT_NAME.strip():
        raise VoiceConfigurationError(
            "VOICE_AGENT_NAME is not configured"
        )


def _resolve_conversation(
    *,
    db: Session,
    user: User,
    mode: ConversationMode,
    conversation_id: str | None,
    title: str,
) -> Conversation:
    user_id = str(user.id)

    if conversation_id is None:
        return create_conversation(
            db=db,
            user_id=user_id,
            title=title,
            mode=mode,
        )

    conversation = get_conversation_for_user(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise VoiceConversationNotFoundError(
            "Conversation not found"
        )

    if conversation.mode != mode:
        raise VoiceConversationModeError(
            "Voice session mode does not match "
            "the conversation mode"
        )

    return conversation


def _validate_documents(
    *,
    db: Session,
    user: User,
    document_ids: tuple[str, ...],
) -> None:
    user_id = str(user.id)

    for document_id in document_ids:
        document = get_user_document(
            db=db,
            user_id=user_id,
            document_id=document_id,
        )

        if document is None:
            raise VoiceDocumentValidationError(
                "One or more selected documents "
                "are not available"
            )

        if document.status != "ready":
            raise VoiceDocumentValidationError(
                "Selected documents must be "
                "processed and ready"
            )


def create_voice_session(
    *,
    db: Session,
    user: User,
    mode: ConversationMode,
    conversation_id: str | None,
    title: str,
    document_ids: tuple[str, ...],
) -> VoiceSessionResult:
    _require_voice_configuration()

    conversation = _resolve_conversation(
        db=db,
        user=user,
        mode=mode,
        conversation_id=conversation_id,
        title=title,
    )

    _validate_documents(
        db=db,
        user=user,
        document_ids=document_ids,
    )

    room_name = (
        f"aqlyra-{conversation.id}-"
        f"{uuid4().hex[:12]}"
    )

    participant_identity = (
        f"user-{user.id}-"
        f"{uuid4().hex[:8]}"
    )

    context = {
        "user_id": str(user.id),
        "conversation_id": (
            str(conversation.id)
        ),
        "mode": conversation.mode,
        "document_ids": list(
            document_ids
        ),
    }

    metadata = json.dumps(
        context,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    token = (
        api.AccessToken(
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        )
        .with_identity(
            participant_identity
        )
        .with_name(user.username)
        .with_metadata(metadata)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=(
                            settings
                            .VOICE_AGENT_NAME
                        ),
                        metadata=metadata,
                    )
                ]
            )
        )
        .to_jwt()
    )

    return VoiceSessionResult(
        server_url=settings.LIVEKIT_URL,
        participant_token=token,
        room_name=room_name,
        conversation_id=(
            str(conversation.id)
        ),
        mode=conversation.mode,
    )
