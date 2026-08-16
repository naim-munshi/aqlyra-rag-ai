from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now_naive
from app.models.conversation import Conversation
from app.models.message import Message


def create_conversation(
    *,
    db: Session,
    user_id: str,
    title: str,
    mode: str,
) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        title=title,
        mode=mode,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def get_conversation_for_user(
    *,
    db: Session,
    user_id: str,
    conversation_id: str,
) -> Conversation | None:
    statement = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )

    return db.scalar(statement)


def list_conversations_for_user(
    *,
    db: Session,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id
        )
        .order_by(
            Conversation.is_pinned.desc(),
            Conversation.updated_at.desc(),
            Conversation.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )


def update_conversation(
    *,
    db: Session,
    conversation: Conversation,
    title: str | None = None,
    mode: str | None = None,
    is_pinned: bool | None = None,
) -> Conversation:
    if title is not None:
        conversation.title = title

    if mode is not None:
        conversation.mode = mode

    if is_pinned is not None:
        conversation.is_pinned = is_pinned

    conversation.updated_at = utc_now_naive()

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def delete_conversation(
    *,
    db: Session,
    conversation: Conversation,
) -> None:
    db.delete(conversation)
    db.commit()


def list_messages_for_conversation(
    *,
    db: Session,
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[Message]:
    statement = (
        select(Message)
        .where(
            Message.conversation_id
            == conversation_id
        )
        .order_by(
            Message.created_at.asc(),
            Message.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )


def get_recent_messages_for_conversation(
    *,
    db: Session,
    conversation_id: str,
    limit: int = 20,
) -> list[Message]:
    statement = (
        select(Message)
        .where(
            Message.conversation_id
            == conversation_id
        )
        .order_by(
            Message.created_at.desc(),
            Message.id.desc(),
        )
        .limit(limit)
    )

    messages = list(
        db.scalars(statement).all()
    )

    messages.reverse()

    return messages


def persist_chat_turn(
    *,
    db: Session,
    conversation: Conversation,
    user_content: str,
    assistant_content: str,
    mode: str,
    provider_name: str,
    model_name: str,
    response_id: str | None,
    citations: list[dict],
    is_refusal: bool,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    evidence_tokens: int | None,
) -> tuple[Message, Message]:
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        mode=mode,
        content=user_content,
        citations=[],
        is_refusal=False,
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        mode=mode,
        content=assistant_content,
        provider_name=provider_name,
        model_name=model_name,
        response_id=response_id,
        citations=citations,
        is_refusal=is_refusal,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        evidence_tokens=evidence_tokens,
    )

    conversation.updated_at = utc_now_naive()

    try:
        db.add_all(
            [
                user_message,
                assistant_message,
                conversation,
            ]
        )
        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(conversation)

    return (
        user_message,
        assistant_message,
    )
