import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.llms import (
    DeterministicLLMProvider,
)
from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.message import Message
from app.models.user import User
from app.services.memory_extraction_service import (
    MemoryExtractionValidationError,
    extract_memories_best_effort,
    extract_memories_for_message,
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


def create_message(
    db: Session,
    *,
    user: User,
    content: str,
    role: str = "user",
) -> Message:
    conversation = Conversation(
        user_id=str(user.id),
        title="Memory extraction test",
        mode="normal",
    )

    db.add(conversation)
    db.flush()

    message = Message(
        conversation_id=conversation.id,
        role=role,
        mode="normal",
        content=content,
        citations=[],
        is_refusal=False,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def provider_for(
    payload: dict,
) -> DeterministicLLMProvider:
    return DeterministicLLMProvider(
        response_text=json.dumps(
            payload,
            ensure_ascii=False,
        )
    )


def test_extracts_valid_durable_memory(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-valid",
    )

    message = create_message(
        db_session,
        user=user,
        content=(
            "I prefer Python over Java."
        ),
    )

    provider = provider_for(
        {
            "memories": [
                {
                    "kind": "preference",
                    "content": (
                        "I prefer Python over Java."
                    ),
                    "importance": 0.8,
                    "confidence": 0.95,
                }
            ]
        }
    )

    memories = (
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider,
        )
    )

    assert len(memories) == 1

    memory = memories[0]

    assert memory.user_id == user.id
    assert memory.kind == "preference"
    assert memory.source_message_id == (
        message.id
    )
    assert memory.content == (
        "I prefer Python over Java."
    )


def test_empty_extraction_writes_nothing(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-empty",
    )

    message = create_message(
        db_session,
        user=user,
        content="Explain recursion.",
    )

    memories = (
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [],
                }
            ),
        )
    )

    assert memories == []

    stored = list(
        db_session.scalars(
            select(Memory).where(
                Memory.user_id
                == str(user.id)
            )
        ).all()
    )

    assert stored == []


def test_low_confidence_candidate_is_not_saved(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-low-confidence",
    )

    message = create_message(
        db_session,
        user=user,
        content="Maybe I like Rust.",
    )

    memories = (
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [
                        {
                            "kind": "preference",
                            "content": (
                                "I like Rust."
                            ),
                            "importance": 0.5,
                            "confidence": 0.4,
                        }
                    ]
                }
            ),
        )
    )

    assert memories == []


def test_duplicate_candidates_collapse_per_turn(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-dedupe",
    )

    message = create_message(
        db_session,
        user=user,
        content="My goal is to learn Rust.",
    )

    candidate = {
        "kind": "goal",
        "content": (
            "My goal is to learn Rust."
        ),
        "importance": 0.8,
        "confidence": 0.95,
    }

    memories = (
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [
                        candidate,
                        candidate,
                    ]
                }
            ),
        )
    )

    assert len(memories) == 1


def test_rejects_document_citation_candidate(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-citation",
    )

    message = create_message(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    with pytest.raises(
        MemoryExtractionValidationError
    ):
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [
                        {
                            "kind": "preference",
                            "content": (
                                "I prefer Python [S1]."
                            ),
                            "importance": 0.8,
                            "confidence": 0.95,
                        }
                    ]
                }
            ),
        )


def test_rejects_foreign_source_message(
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        suffix="extract-owner",
    )

    attacker = create_user(
        db_session,
        suffix="extract-attacker",
    )

    message = create_message(
        db_session,
        user=owner,
        content="I prefer Python.",
    )

    with pytest.raises(
        MemoryExtractionValidationError
    ):
        extract_memories_for_message(
            db=db_session,
            user_id=str(attacker.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [],
                }
            ),
        )


def test_rejects_assistant_source_message(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-assistant",
    )

    message = create_message(
        db_session,
        user=user,
        role="assistant",
        content="You prefer Python.",
    )

    with pytest.raises(
        MemoryExtractionValidationError
    ):
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [],
                }
            ),
        )


def test_best_effort_failure_does_not_raise(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-best-effort",
    )

    message = create_message(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_AUTO_EXTRACT_ENABLED",
        True,
    )

    invalid_provider = (
        DeterministicLLMProvider(
            response_text="not-json"
        )
    )

    memories = (
        extract_memories_best_effort(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=invalid_provider,
        )
    )

    assert memories == []

    persisted = list(
        db_session.scalars(
            select(Memory).where(
                Memory.user_id
                == str(user.id)
            )
        ).all()
    )

    assert persisted == []


@pytest.mark.parametrize(
    "secret_content",
    [
        "My password is hunter2-secret",
        "My API key: sk-abcdefghijklmnopqrstuv",
        "Use Bearer abcdefghijklmnopqrstuvwxyz",
        "My card is 4111 1111 1111 1111",
    ],
)
def test_rejects_sensitive_memory_candidate(
    db_session: Session,
    secret_content: str,
) -> None:
    user = create_user(
        db_session,
        suffix=(
            "extract-secret-"
            + str(
                abs(hash(secret_content))
            )
        ),
    )

    message = create_message(
        db_session,
        user=user,
        content="Store my credential.",
    )

    with pytest.raises(
        MemoryExtractionValidationError
    ):
        extract_memories_for_message(
            db=db_session,
            user_id=str(user.id),
            source_message_id=message.id,
            provider=provider_for(
                {
                    "memories": [
                        {
                            "kind": "fact",
                            "content": secret_content,
                            "importance": 0.9,
                            "confidence": 0.99,
                        }
                    ]
                }
            ),
        )


def test_disabled_auto_extraction_skips_provider(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="extract-disabled",
    )

    message = create_message(
        db_session,
        user=user,
        content="I prefer Python.",
    )

    class TrackingProvider:
        called = False

        def generate(
            self,
            *,
            instructions: str,
            input_text: str,
        ):
            self.called = True
            raise AssertionError(
                "Provider must not be called"
            )

    provider = TrackingProvider()

    monkeypatch.setattr(
        settings,
        "MEMORY_AUTO_EXTRACT_ENABLED",
        False,
    )

    result = extract_memories_best_effort(
        db=db_session,
        user_id=str(user.id),
        source_message_id=message.id,
        provider=provider,
    )

    assert result == []
    assert provider.called is False
