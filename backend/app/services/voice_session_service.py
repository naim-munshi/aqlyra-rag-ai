import asyncio
import json
import ipaddress
import logging
from urllib.parse import urlsplit
from datetime import timedelta
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

logger = logging.getLogger(__name__)


class VoiceConfigurationError(
    RuntimeError
):
    pass


class VoiceDispatchUnavailableError(VoiceConfigurationError):
    """Do not expose LiveKit transport or credential errors to a browser."""


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


def _valid_livekit_url(url: str, *, production: bool) -> bool:
    """Keep room tokens off plaintext, loopback and misleading endpoints."""
    try:
        parsed = urlsplit(url.strip())
        host = parsed.hostname
        if (
            not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or parsed.scheme not in (("wss",) if production else ("ws", "wss"))
        ):
            return False
        if production:
            normalized = host.lower().rstrip(".")
            if normalized != host.lower() or normalized in ("localhost",) or normalized.endswith(
                (".localhost", ".local", ".internal")
            ):
                return False
            try:
                if not ipaddress.ip_address(normalized).is_global:
                    return False
            except ValueError:
                if "." not in normalized:
                    return False
        # Verify even an explicit port has valid syntax/range.
        if parsed.port is not None and parsed.port <= 0:
            return False
        return True
    except ValueError:
        return False


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
            ("VOICE_STT_MODEL", settings.VOICE_STT_MODEL),
            ("VOICE_STT_LANGUAGE", settings.VOICE_STT_LANGUAGE),
            ("VOICE_SESSION_LLM_MODEL", settings.VOICE_SESSION_LLM_MODEL),
            ("VOICE_TTS_MODEL", settings.VOICE_TTS_MODEL),
            ("VOICE_TTS_VOICE", settings.VOICE_TTS_VOICE),
        )
        if not value.strip()
    ]

    if (
        settings.VOICE_STT_PROVIDER == "groq"
        or settings.VOICE_SESSION_LLM_PROVIDER == "groq"
        or settings.LLM_PROVIDER == "groq"
    ) and not settings.GROQ_API_KEY.strip():
        missing.append("GROQ_API_KEY")

    if missing:
        raise VoiceConfigurationError(
            "Voice service is not configured"
        )

    if not _valid_livekit_url(
        settings.LIVEKIT_URL, production=settings.APP_ENV == "production",
    ):
        raise VoiceConfigurationError("Voice transport is not safely configured")

    if not settings.VOICE_AGENT_NAME.strip():
        raise VoiceConfigurationError(
            "VOICE_AGENT_NAME is not configured"
        )

    if not settings.VOICE_AGENT_READY:
        raise VoiceConfigurationError(
            "Voice service is not configured or enabled"
        )


def missing_voice_configuration_keys() -> tuple[str, ...]:
    """Operator diagnostic: names only, never credentials or token values.

    This list is for private production logs and can identify why the
    authenticated status route reports unavailable without leaking secrets.
    It is deliberately not returned to end users.
    """
    checks = {
        "LIVEKIT_URL": settings.LIVEKIT_URL,
        "LIVEKIT_API_KEY": settings.LIVEKIT_API_KEY,
        "LIVEKIT_API_SECRET": settings.LIVEKIT_API_SECRET,
        "VOICE_AGENT_NAME": settings.VOICE_AGENT_NAME,
        "VOICE_STT_MODEL": settings.VOICE_STT_MODEL,
        "VOICE_STT_LANGUAGE": settings.VOICE_STT_LANGUAGE,
        "VOICE_SESSION_LLM_MODEL": settings.VOICE_SESSION_LLM_MODEL,
        "VOICE_TTS_MODEL": settings.VOICE_TTS_MODEL,
        "VOICE_TTS_VOICE": settings.VOICE_TTS_VOICE,
    }
    missing = [name for name, value in checks.items() if not value.strip()]
    if not settings.VOICE_AGENT_READY:
        missing.append("VOICE_AGENT_READY")
    if not _valid_livekit_url(
        settings.LIVEKIT_URL, production=settings.APP_ENV == "production"
    ):
        missing.append("LIVEKIT_URL_INVALID")
    if (
        settings.VOICE_STT_PROVIDER == "groq"
        or settings.VOICE_SESSION_LLM_PROVIDER == "groq"
        or settings.LLM_PROVIDER == "groq"
    ) and not settings.GROQ_API_KEY.strip():
        missing.append("GROQ_API_KEY")
    return tuple(dict.fromkeys(missing))


def voice_is_ready() -> bool:
    """Server-side readiness contract; never expose LiveKit credentials."""
    try:
        _require_voice_configuration()
    except VoiceConfigurationError:
        return False
    return True


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


async def _create_explicit_voice_dispatch(
    *, room_name: str, metadata: str,
) -> None:
    # Explicit server-side dispatch avoids silent token-only room-config
    # failures; the one-time room UUID prevents cross-session reuse.
    lkapi = api.LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    try:
        await asyncio.wait_for(
            lkapi.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=settings.VOICE_AGENT_NAME,
                    room=room_name,
                    metadata=metadata,
                )
            ),
            timeout=8.0,
        )
    finally:
        await lkapi.aclose()


def _dispatch_voice_agent(
    *, room_name: str, metadata: str,
) -> None:
    # FastAPI runs the sync endpoint in a worker thread. Never execute
    # network requests on the application's event loop.
    try:
        asyncio.run(
            _create_explicit_voice_dispatch(
                room_name=room_name, metadata=metadata,
            )
        )
    except Exception as exc:
        # Error type only: provider exceptions may contain private tokens.
        logger.warning(
            "voice_dispatch_request_failed error_type=%s",
            type(exc).__name__,
        )
        raise VoiceDispatchUnavailableError(
            "Voice agent could not be started. Please retry later."
        ) from None
    logger.info("voice_dispatch_request_accepted")


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

    # Reject foreign or unprocessed documents before creating a
    # persistent conversation (no abandoned conversations on 422).
    _validate_documents(
        db=db,
        user=user,
        document_ids=document_ids,
    )

    conversation = _resolve_conversation(
        db=db,
        user=user,
        mode=mode,
        conversation_id=conversation_id,
        title=title,
    )

    # Opaque identifiers: never put stable account/conversation IDs in
    # LiveKit room or participant identities (both appear in RTC logs).
    room_name = f"aqlyra-voice-{uuid4().hex}"
    participant_identity = f"voice-{uuid4().hex}"

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
        .with_name("Aqlyra Voice")
        # Short-lived joining authority: an active session may continue.
        # Do not rely on LiveKit's longer SDK default TTL.
        .with_ttl(timedelta(minutes=10))
        # Do not copy private owner/document IDs into visible participant
        # metadata. Only the named agent dispatch receives job metadata.
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_publish_sources=["microphone"],
                can_subscribe=True,
                can_publish_data=False,
                can_update_own_metadata=False,
            )
        )
        .to_jwt()
    )

    # The API dispatches exactly once before sending a participant token.
    # Do not also add RoomConfiguration.agents to the token (duplicate jobs).
    _dispatch_voice_agent(room_name=room_name, metadata=metadata)

    return VoiceSessionResult(
        server_url=settings.LIVEKIT_URL,
        participant_token=token,
        room_name=room_name,
        conversation_id=(
            str(conversation.id)
        ),
        mode=conversation.mode,
    )
