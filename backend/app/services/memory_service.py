from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now_naive
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding


class MemoryValidationError(ValueError):
    pass


def normalize_memory_content(
    content: str,
) -> tuple[str, str]:
    cleaned = " ".join(
        content.split()
    )

    if not cleaned:
        raise MemoryValidationError(
            "Memory content cannot be empty"
        )

    normalized = cleaned.casefold()

    return cleaned, normalized


def create_memory(
    *,
    db: Session,
    user_id: str,
    kind: str,
    content: str,
    importance: float = 0.5,
    confidence: float = 1.0,
    source_message_id: str | None = None,
) -> Memory:
    cleaned, normalized = (
        normalize_memory_content(content)
    )

    memory = Memory(
        user_id=user_id,
        kind=kind,
        content=cleaned,
        normalized_content=normalized,
        importance=importance,
        confidence=confidence,
        source_message_id=source_message_id,
    )

    try:
        db.add(memory)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(memory)

    return memory


def get_memory_for_user(
    *,
    db: Session,
    user_id: str,
    memory_id: str,
) -> Memory | None:
    statement = (
        select(Memory)
        .where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )
    )

    return db.scalar(statement)


def list_memories_for_user(
    *,
    db: Session,
    user_id: str,
    kind: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Memory]:
    statement = select(Memory).where(
        Memory.user_id == user_id
    )

    if kind is not None:
        statement = statement.where(
            Memory.kind == kind
        )

    if is_active is not None:
        statement = statement.where(
            Memory.is_active == is_active
        )

    statement = (
        statement
        .order_by(
            Memory.updated_at.desc(),
            Memory.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )


def update_memory(
    *,
    db: Session,
    memory: Memory,
    kind: str | None = None,
    content: str | None = None,
    importance: float | None = None,
    confidence: float | None = None,
    is_active: bool | None = None,
) -> Memory:
    content_changed = False

    if kind is not None:
        memory.kind = kind

    if content is not None:
        cleaned, normalized = (
            normalize_memory_content(
                content
            )
        )

        content_changed = (
            cleaned != memory.content
        )

        memory.content = cleaned
        memory.normalized_content = normalized

    if importance is not None:
        memory.importance = importance

    if confidence is not None:
        memory.confidence = confidence

    if is_active is not None:
        memory.is_active = is_active

    memory.updated_at = utc_now_naive()

    try:
        if content_changed:
            db.execute(
                delete(
                    MemoryEmbedding
                ).where(
                    MemoryEmbedding.memory_id
                    == memory.id
                )
            )

        db.add(memory)
        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(memory)

    return memory


def delete_memory(
    *,
    db: Session,
    memory: Memory,
) -> None:
    try:
        db.delete(memory)
        db.commit()

    except Exception:
        db.rollback()
        raise
