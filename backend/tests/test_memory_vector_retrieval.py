import hashlib
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from app.embeddings.types import (
    EmbeddingProviderInfo,
)
from app.llms import (
    DeterministicLLMProvider,
)
from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.message import Message
from app.models.user import User
from app.services.memory_embedding_service import (
    MemoryEmbeddingDimensionError,
    MemoryEmbeddingValidationError,
    index_memory_embeddings,
)
from app.services.memory_extraction_service import (
    extract_memories_best_effort,
)
from app.services.memory_retrieval_service import (
    MemoryRetrievalValidationError,
    retrieve_memories_for_user,
)
from app.services.memory_service import (
    create_memory,
)


def create_user(
    db: Session,
    *,
    suffix: str,
) -> User:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        hashed_password="test-password-hash",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_test_memory(
    db: Session,
    *,
    user: User,
    content: str,
    kind: str = "preference",
) -> Memory:
    return create_memory(
        db=db,
        user_id=str(user.id),
        kind=kind,
        content=content,
        importance=0.8,
        confidence=0.95,
    )


def test_memory_embedding_is_persisted(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-vector-persist",
    )

    memory = create_test_memory(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    records = index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[memory.id],
    )

    assert len(records) == 1

    record = records[0]

    assert record.memory_id == memory.id
    assert record.provider_name == (
        "deterministic"
    )
    assert record.model_name == (
        "deterministic-sha256-v1"
    )
    assert record.dimension == 384
    assert len(list(record.embedding)) == 384

    assert record.content_hash == (
        hashlib.sha256(
            memory.content.encode("utf-8")
        ).hexdigest()
    )

    assert record.embedding_metadata[
        "source"
    ] == "personal_memory"


def test_reindex_replaces_same_provider_model(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-vector-reindex",
    )

    memory = create_test_memory(
        db_session,
        user=user,
        content="I prefer PostgreSQL.",
    )

    first = index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[memory.id],
    )

    second = index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[memory.id],
    )

    assert len(first) == 1
    assert len(second) == 1

    count = db_session.scalar(
        select(
            func.count(
                MemoryEmbedding.id
            )
        ).where(
            MemoryEmbedding.memory_id
            == memory.id
        )
    )

    assert count == 1


def test_memory_indexing_enforces_ownership(
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        suffix="memory-index-owner",
    )

    attacker = create_user(
        db_session,
        suffix="memory-index-attacker",
    )

    memory = create_test_memory(
        db_session,
        user=owner,
        content="My private preference.",
    )

    with pytest.raises(
        MemoryEmbeddingValidationError
    ):
        index_memory_embeddings(
            db=db_session,
            user_id=str(attacker.id),
            memory_ids=[memory.id],
        )

    count = db_session.scalar(
        select(
            func.count(
                MemoryEmbedding.id
            )
        ).where(
            MemoryEmbedding.memory_id
            == memory.id
        )
    )

    assert count == 0


def test_exact_memory_is_top_retrieval_hit(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-retrieval-exact",
    )

    target = create_test_memory(
        db_session,
        user=user,
        content=(
            "I prefer distributed systems."
        ),
    )

    other = create_test_memory(
        db_session,
        user=user,
        content=(
            "My goal is to learn Japanese."
        ),
        kind="goal",
    )

    index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[
            target.id,
            other.id,
        ],
    )

    hits = retrieve_memories_for_user(
        db=db_session,
        user_id=str(user.id),
        query_text=target.content,
        top_k=2,
    )

    assert hits
    assert hits[0].memory_id == target.id
    assert hits[0].content == target.content
    assert hits[0].similarity_score == (
        pytest.approx(
            1.0,
            abs=1e-5,
        )
    )


def test_memory_retrieval_enforces_user_isolation(
    db_session: Session,
) -> None:
    first_user = create_user(
        db_session,
        suffix="memory-retrieval-first",
    )

    second_user = create_user(
        db_session,
        suffix="memory-retrieval-second",
    )

    first_memory = create_test_memory(
        db_session,
        user=first_user,
        content="First user's private memory.",
    )

    second_memory = create_test_memory(
        db_session,
        user=second_user,
        content="Second user's private memory.",
    )

    index_memory_embeddings(
        db=db_session,
        user_id=str(first_user.id),
        memory_ids=[first_memory.id],
    )

    index_memory_embeddings(
        db=db_session,
        user_id=str(second_user.id),
        memory_ids=[second_memory.id],
    )

    hits = retrieve_memories_for_user(
        db=db_session,
        user_id=str(first_user.id),
        query_text=second_memory.content,
        top_k=10,
    )

    assert hits

    assert all(
        hit.memory_id != second_memory.id
        for hit in hits
    )

    assert all(
        hit.memory_id == first_memory.id
        for hit in hits
    )


def test_inactive_memory_is_not_retrieved(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-retrieval-inactive",
    )

    inactive = create_test_memory(
        db_session,
        user=user,
        content="I prefer Rust.",
    )

    active = create_test_memory(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[
            inactive.id,
            active.id,
        ],
    )

    inactive.is_active = False
    db_session.add(inactive)
    db_session.commit()

    hits = retrieve_memories_for_user(
        db=db_session,
        user_id=str(user.id),
        query_text=inactive.content,
        top_k=10,
    )

    assert all(
        hit.memory_id != inactive.id
        for hit in hits
    )


def test_reindex_failure_preserves_existing_index_and_text(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-reindex-failure",
    )

    memory = create_test_memory(
        db_session,
        user=user,
        content="My durable preference.",
    )

    original = index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[memory.id],
    )[0]

    original_id = original.id

    # Force the persisted index to be stale so the
    # service must attempt a replacement embedding.
    original.content_hash = "0" * 64
    db_session.add(original)
    db_session.commit()

    class FailingProvider:
        @property
        def info(self) -> EmbeddingProviderInfo:
            return EmbeddingProviderInfo(
                provider_name="deterministic",
                model_name=(
                    "deterministic-sha256-v1"
                ),
                dimension=384,
                max_batch_size=128,
            )

        def embed_documents(
            self,
            texts,
        ):
            raise RuntimeError(
                "simulated embedding failure"
            )

        def embed_query(
            self,
            text,
        ):
            raise RuntimeError(
                "not used"
            )

    with pytest.raises(RuntimeError):
        index_memory_embeddings(
            db=db_session,
            user_id=str(user.id),
            memory_ids=[memory.id],
            provider=FailingProvider(),
        )

    db_session.expire_all()

    assert db_session.get(
        Memory,
        memory.id,
    ) is not None

    assert db_session.get(
        Memory,
        memory.id,
    ).content == (
        "My durable preference."
    )

    assert db_session.get(
        MemoryEmbedding,
        original_id,
    ) is not None


def test_wrong_embedding_dimension_is_rejected(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-wrong-dimension",
    )

    memory = create_test_memory(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=128,
        )
    )

    with pytest.raises(
        MemoryEmbeddingDimensionError
    ):
        index_memory_embeddings(
            db=db_session,
            user_id=str(user.id),
            memory_ids=[memory.id],
            provider=provider,
        )


def test_memory_retrieval_validates_query(
    db_session: Session,
) -> None:
    with pytest.raises(
        MemoryRetrievalValidationError
    ):
        retrieve_memories_for_user(
            db=db_session,
            user_id="user-1",
            query_text="   ",
        )

    with pytest.raises(
        MemoryRetrievalValidationError
    ):
        retrieve_memories_for_user(
            db=db_session,
            user_id="user-1",
            query_text="test",
            top_k=0,
        )


def test_best_effort_extraction_indexes_memory(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-auto-index",
    )

    conversation = Conversation(
        user_id=str(user.id),
        title="Memory indexing integration",
        mode="normal",
    )

    db_session.add(conversation)
    db_session.flush()

    message = Message(
        conversation_id=conversation.id,
        role="user",
        mode="normal",
        content="I prefer Python.",
        citations=[],
        is_refusal=False,
    )

    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    monkeypatch.setattr(
        settings,
        "MEMORY_AUTO_EXTRACT_ENABLED",
        True,
    )

    provider = DeterministicLLMProvider(
        response_text=json.dumps(
            {
                "memories": [
                    {
                        "kind": "preference",
                        "content": (
                            "I prefer Python."
                        ),
                        "importance": 0.8,
                        "confidence": 0.95,
                    }
                ]
            }
        )
    )

    memories = extract_memories_best_effort(
        db=db_session,
        user_id=str(user.id),
        source_message_id=message.id,
        provider=provider,
    )

    assert len(memories) == 1

    embedding = db_session.scalar(
        select(
            MemoryEmbedding
        ).where(
            MemoryEmbedding.memory_id
            == memories[0].id
        )
    )

    assert embedding is not None
    assert embedding.content_hash == (
        hashlib.sha256(
            memories[0]
            .content
            .encode("utf-8")
        ).hexdigest()
    )


def test_unchanged_memory_embedding_is_reused(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-vector-idempotent",
    )

    memory = create_test_memory(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    class CountingProvider(
        DeterministicHashEmbeddingProvider
    ):
        def __init__(self) -> None:
            super().__init__(
                dimension=384
            )
            self.document_calls = 0

        def embed_documents(
            self,
            texts,
        ):
            self.document_calls += 1

            return super().embed_documents(
                texts
            )

    provider = CountingProvider()

    first = index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[memory.id],
        provider=provider,
    )

    second = index_memory_embeddings(
        db=db_session,
        user_id=str(user.id),
        memory_ids=[memory.id],
        provider=provider,
    )

    assert provider.document_calls == 1
    assert first[0].id == second[0].id
