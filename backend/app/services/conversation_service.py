from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now_naive
from app.models.conversation import Conversation


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
) -> Conversation:
    if title is not None:
        conversation.title = title

    if mode is not None:
        conversation.mode = mode

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
