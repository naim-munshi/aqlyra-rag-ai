import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
)
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.message import Message
from app.models.user import User


def create_memory_graph(
    db: Session,
    *,
    suffix: str,
) -> tuple[
    User,
    Conversation,
    Message,
    Memory,
    MemoryEmbedding,
]:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        hashed_password="test-password-hash",
    )

    db.add(user)
    db.flush()

    conversation = Conversation(
        user_id=user.id,
        title="Memory test",
        mode="normal",
    )

    db.add(conversation)
    db.flush()

    message = Message(
        conversation_id=conversation.id,
        role="user",
        mode="normal",
        content="I prefer dark mode.",
    )

    db.add(message)
    db.flush()

    content = "The user prefers dark mode."

    memory = Memory(
        user_id=user.id,
        kind="preference",
        content=content,
        normalized_content=(
            "user prefers dark mode"
        ),
        importance=0.8,
        confidence=0.95,
        source_message_id=message.id,
    )

    db.add(memory)
    db.flush()

    embedding = MemoryEmbedding(
        memory_id=memory.id,
        provider_name="deterministic",
        model_name="deterministic-384",
        dimension=EMBEDDING_DIMENSION,
        embedding=[
            0.0
            for _ in range(
                EMBEDDING_DIMENSION
            )
        ],
        content_hash=hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
        input_token_count=5,
        estimated_cost_usd=0.0,
        embedding_metadata={
            "test": True,
        },
    )

    db.add(embedding)
    db.commit()

    db.refresh(user)
    db.refresh(conversation)
    db.refresh(message)
    db.refresh(memory)
    db.refresh(embedding)

    return (
        user,
        conversation,
        message,
        memory,
        embedding,
    )


def test_memory_and_embedding_persist_separately(
    db_session: Session,
) -> None:
    (
        _user,
        _conversation,
        _message,
        memory,
        embedding,
    ) = create_memory_graph(
        db_session,
        suffix="memory-separate",
    )

    memory_id = memory.id
    embedding_id = embedding.id

    db_session.delete(embedding)
    db_session.commit()

    assert (
        db_session.get(
            MemoryEmbedding,
            embedding_id,
        )
        is None
    )

    persisted_memory = db_session.get(
        Memory,
        memory_id,
    )

    assert persisted_memory is not None
    assert persisted_memory.content == (
        "The user prefers dark mode."
    )
    assert persisted_memory.is_active is True


def test_deleting_source_message_keeps_memory(
    db_session: Session,
) -> None:
    (
        _user,
        _conversation,
        message,
        memory,
        _embedding,
    ) = create_memory_graph(
        db_session,
        suffix="memory-source-delete",
    )

    memory_id = memory.id

    db_session.delete(message)
    db_session.commit()
    db_session.expire_all()

    persisted_memory = db_session.get(
        Memory,
        memory_id,
    )

    assert persisted_memory is not None
    assert (
        persisted_memory.source_message_id
        is None
    )
    assert persisted_memory.content == (
        "The user prefers dark mode."
    )


def test_deleting_user_cascades_memory_and_embedding(
    db_session: Session,
) -> None:
    (
        user,
        _conversation,
        _message,
        memory,
        embedding,
    ) = create_memory_graph(
        db_session,
        suffix="memory-user-delete",
    )

    memory_id = memory.id
    embedding_id = embedding.id

    db_session.delete(user)
    db_session.commit()
    db_session.expire_all()

    assert (
        db_session.scalar(
            select(Memory).where(
                Memory.id == memory_id
            )
        )
        is None
    )

    assert (
        db_session.scalar(
            select(MemoryEmbedding).where(
                MemoryEmbedding.id
                == embedding_id
            )
        )
        is None
    )


def test_memory_embedding_uses_database_dimension() -> None:
    vector_type = (
        MemoryEmbedding
        .__table__
        .c
        .embedding
        .type
    )

    assert vector_type.dim == (
        EMBEDDING_DIMENSION
    )
    assert EMBEDDING_DIMENSION == 384
