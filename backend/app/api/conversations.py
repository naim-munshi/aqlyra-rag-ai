import json

from fastapi.responses import StreamingResponse
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
from app.core.logging import app_logger
from app.core.rate_limit import (
    limit_chat_request,
)
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
from app.schemas.conversation import (
    ChatTurnResponse,
    ConversationCreate,
    ConversationMessageCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.services.chat_service import (
    ChatValidationError,
    execute_chat_turn,
    stream_normal_chat_reply,
)
from app.services.memory_extraction_service import (
    extract_memories_best_effort,
)
from app.services.conversation_document_service import (
    ConversationDocumentScopeError,
    resolve_conversation_document_scope,
)
from app.services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation_for_user,
    list_conversations_for_user,
    list_messages_for_conversation,
    persist_chat_turn,
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
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def list_messages_endpoint(
    conversation_id: str,
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> list[MessageResponse]:
    conversation = get_conversation_for_user(
        db=db,
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise _conversation_not_found()

    return list_messages_for_conversation(
        db=db,
        conversation_id=conversation.id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ChatTurnResponse,
    dependencies=[
        Depends(limit_chat_request),
    ],
)
def create_message_endpoint(
    conversation_id: str,
    request: ConversationMessageCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> ChatTurnResponse:
    conversation = get_conversation_for_user(
        db=db,
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise _conversation_not_found()

    try:
        document_scope = (
            resolve_conversation_document_scope(
                db=db,
                conversation=conversation,
                requested_document_ids=tuple(
                    request.document_ids
                ),
            )
        )

        result = execute_chat_turn(
            db=db,
            conversation=conversation,
            message=request.content,
            document_ids=(
                document_scope
                .effective_document_ids
            ),
            top_k=request.top_k,
        )

    except (
        RetrievalValidationError,
        ChatValidationError,
        ConversationDocumentScopeError,
    ) as exc:
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
            "Conversation provider "
            "configuration failed: "
            f"conversation_id={conversation.id}"
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Conversation provider "
                "configuration failed"
            ),
        ) from exc

    except (
        EmbeddingError,
        LLMProviderRequestError,
    ) as exc:
        app_logger.exception(
            "Conversation provider request failed: "
            f"conversation_id={conversation.id}"
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Conversation provider service "
                "is unavailable"
            ),
        ) from exc

    except (
        LLMProviderResponseError,
        CitationValidationError,
        GroundedAnswerError,
    ) as exc:
        app_logger.exception(
            "Conversation answer validation failed: "
            f"conversation_id={conversation.id}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "The generated conversation answer "
                "failed validation"
            ),
        ) from exc

    user_message, assistant_message = (
        persist_chat_turn(
            db=db,
            conversation=conversation,
            user_content=(
                request.display_content
                if request.display_content
                is not None
                else request.content
            ),
            assistant_content=result.content,
            mode=result.mode,
            provider_name=(
                result.provider_name
            ),
            model_name=result.model_name,
            response_id=result.response_id,
            citations=list(
                result.citations
            ),
            is_refusal=result.is_refusal,
            input_tokens=result.input_tokens,
            output_tokens=(
                result.output_tokens
            ),
            total_tokens=(
                result.total_tokens
            ),
            evidence_tokens=(
                result.evidence_tokens
            ),
            scope_document_ids=(
                document_scope
                .new_document_ids
            ),
            attachment_document_ids=tuple(
                request.document_ids
            ),
        )
    )

    extract_memories_best_effort(
        db=db,
        user_id=str(current_user.id),
        source_message_id=user_message.id,
    )

    return ChatTurnResponse(
        conversation_id=conversation.id,
        mode=conversation.mode,
        user_message=user_message,
        assistant_message=assistant_message,
    )



def _encode_stream_event(
    event_name: str,
    payload: dict,
) -> str:
    data = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return (
        f"event: {event_name}\n"
        f"data: {data}\n\n"
    )


@router.post(
    "/{conversation_id}/messages/stream",
    dependencies=[
        Depends(limit_chat_request),
    ],
)
def create_message_stream_endpoint(
    conversation_id: str,
    request: ConversationMessageCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    conversation = get_conversation_for_user(
        db=db,
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise _conversation_not_found()

    if conversation.mode != "normal":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Streaming currently supports "
                "normal conversations only"
            ),
        )

    user_id = str(current_user.id)
    user_content = request.content
    user_display_content = (
        request.display_content
        if request.display_content
        is not None
        else request.content
    )

    def event_stream():
        yield _encode_stream_event(
            "start",
            {
                "conversation_id": (
                    conversation.id
                ),
                "mode": "normal",
            },
        )

        try:
            generation = None

            if request.document_ids:
                result = execute_chat_turn(
                    db=db,
                    conversation=conversation,
                    message=user_content,
                    document_ids=tuple(
                        request.document_ids
                    ),
                    top_k=request.top_k,
                )

                if result.content:
                    yield _encode_stream_event(
                        "delta",
                        {
                            "text": result.content,
                        },
                    )

                (
                    user_message,
                    assistant_message,
                ) = persist_chat_turn(
                    db=db,
                    conversation=conversation,
                    user_content=(
                        user_display_content
                    ),
                    assistant_content=(
                        result.content
                    ),
                    mode=result.mode,
                    provider_name=(
                        result.provider_name
                    ),
                    model_name=(
                        result.model_name
                    ),
                    response_id=(
                        result.response_id
                    ),
                    citations=list(
                        result.citations
                    ),
                    is_refusal=(
                        result.is_refusal
                    ),
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
                    attachment_document_ids=tuple(
                        request.document_ids
                    ),
                )

                if user_display_content:
                    extract_memories_best_effort(
                        db=db,
                        user_id=user_id,
                        source_message_id=(
                            user_message.id
                        ),
                    )

                completed = ChatTurnResponse(
                    conversation_id=(
                        conversation.id
                    ),
                    mode="normal",
                    user_message=user_message,
                    assistant_message=(
                        assistant_message
                    ),
                )

                yield _encode_stream_event(
                    "complete",
                    completed.model_dump(
                        mode="json"
                    ),
                )

                return

            for event in stream_normal_chat_reply(
                db=db,
                conversation=conversation,
                message=user_content,
            ):
                if (
                    event.event_type
                    == "delta"
                ):
                    if event.delta_text:
                        yield _encode_stream_event(
                            "delta",
                            {
                                "text": (
                                    event.delta_text
                                ),
                            },
                        )

                    continue

                if (
                    event.event_type
                    == "complete"
                ):
                    generation = (
                        event.generation
                    )

            if generation is None:
                raise (
                    LLMProviderResponseError(
                        "Conversation stream "
                        "ended without completion"
                    )
                )

            (
                user_message,
                assistant_message,
            ) = persist_chat_turn(
                db=db,
                conversation=conversation,
                user_content=(
                    user_display_content
                ),
                assistant_content=(
                    generation.text
                ),
                mode="normal",
                provider_name=(
                    generation.provider_name
                ),
                model_name=(
                    generation.model_name
                ),
                response_id=(
                    generation.response_id
                ),
                citations=[],
                is_refusal=False,
                input_tokens=(
                    generation.input_tokens
                ),
                output_tokens=(
                    generation.output_tokens
                ),
                total_tokens=(
                    generation.total_tokens
                ),
                evidence_tokens=None,
            )

            extract_memories_best_effort(
                db=db,
                user_id=user_id,
                source_message_id=(
                    user_message.id
                ),
            )

            completed = ChatTurnResponse(
                conversation_id=(
                    conversation.id
                ),
                mode="normal",
                user_message=user_message,
                assistant_message=(
                    assistant_message
                ),
            )

            yield _encode_stream_event(
                "complete",
                completed.model_dump(
                    mode="json"
                ),
            )

        except ChatValidationError as exc:
            app_logger.info(
                "Conversation attachment "
                "validation failed: "
                f"conversation_id="
                f"{conversation.id}"
            )

            yield _encode_stream_event(
                "error",
                {
                    "status": 422,
                    "code": (
                        "conversation_validation_error"
                    ),
                    "detail": str(exc),
                },
            )

        except LLMValidationError:
            app_logger.exception(
                "Conversation stream provider "
                "configuration failed: "
                f"conversation_id="
                f"{conversation.id}"
            )

            yield _encode_stream_event(
                "error",
                {
                    "status": 500,
                    "code": (
                        "provider_configuration_failed"
                    ),
                    "detail": (
                        "Conversation provider "
                        "configuration failed"
                    ),
                },
            )

        except LLMProviderRequestError:
            app_logger.exception(
                "Conversation stream provider "
                "request failed: "
                f"conversation_id="
                f"{conversation.id}"
            )

            yield _encode_stream_event(
                "error",
                {
                    "status": 503,
                    "code": (
                        "provider_unavailable"
                    ),
                    "detail": (
                        "Conversation provider "
                        "service is unavailable"
                    ),
                },
            )

        except LLMProviderResponseError:
            app_logger.exception(
                "Conversation stream response "
                "validation failed: "
                f"conversation_id="
                f"{conversation.id}"
            )

            yield _encode_stream_event(
                "error",
                {
                    "status": 502,
                    "code": (
                        "provider_response_invalid"
                    ),
                    "detail": (
                        "The generated conversation "
                        "answer failed validation"
                    ),
                },
            )

        except Exception:
            app_logger.exception(
                "Conversation stream failed: "
                f"conversation_id="
                f"{conversation.id}"
            )

            yield _encode_stream_event(
                "error",
                {
                    "status": 500,
                    "code": "internal_error",
                    "detail": (
                        "Conversation streaming "
                        "failed"
                    ),
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
        is_pinned=request.is_pinned,
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
