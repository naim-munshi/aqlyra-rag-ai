import json

import pytest
from sqlalchemy.orm import Session

import app.services.chat_service as chat_module

from app.config.settings import settings
from app.llms import (
    LLMGeneration,
    LLMProviderInfo,
)
from app.models.conversation import Conversation
from app.models.user import User
from app.services.chat_service import (
    generate_normal_chat_reply,
)
from app.services.memory_retrieval_service import (
    MemoryRetrievalHit,
)


class CapturingProvider:
    def __init__(self) -> None:
        self.instructions: str | None = None
        self.input_text: str | None = None

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="memory-chat-test",
            model_name="memory-chat-test-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        self.instructions = instructions
        self.input_text = input_text

        return LLMGeneration(
            text="Memory-aware response.",
            provider_name="memory-chat-test",
            model_name="memory-chat-test-v1",
            response_id="memory-chat-response",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
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


def create_conversation(
    db: Session,
    *,
    user: User,
) -> Conversation:
    conversation = Conversation(
        user_id=str(user.id),
        title="Normal memory chat",
        mode="normal",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def memory_hit(
    *,
    memory_id: str = "memory-1",
    kind: str = "preference",
    content: str = "I prefer Python.",
) -> MemoryRetrievalHit:
    return MemoryRetrievalHit(
        memory_id=memory_id,
        kind=kind,
        content=content,
        importance=0.8,
        confidence=0.95,
        similarity_score=0.91,
        cosine_distance=0.09,
    )


def test_normal_chat_injects_relevant_memory(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="normal-memory-context",
    )

    conversation = create_conversation(
        db_session,
        user=user,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        True,
    )

    captured: dict = {}

    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return [
            memory_hit(),
        ]

    monkeypatch.setattr(
        chat_module,
        "retrieve_memories_for_user",
        fake_retrieve,
    )

    provider = CapturingProvider()

    result = generate_normal_chat_reply(
        db=db_session,
        conversation=conversation,
        message="Which language should I use?",
        provider=provider,
    )

    assert captured["user_id"] == str(user.id)
    assert captured["query_text"] == (
        "Which language should I use?"
    )
    assert captured["top_k"] == (
        settings.MEMORY_CHAT_TOP_K
    )
    assert captured["min_similarity"] == (
        settings.MEMORY_CHAT_MIN_SIMILARITY
    )

    payload = json.loads(
        provider.input_text
    )

    assert payload[
        "personal_memory_context"
    ] == [
        {
            "kind": "preference",
            "content": "I prefer Python.",
        }
    ]

    serialized = provider.input_text

    assert "memory-1" not in serialized
    assert "0.91" not in serialized
    assert "0.09" not in serialized

    assert result.citations == ()
    assert result.mode == "normal"


def test_memory_disabled_skips_retrieval(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="normal-memory-disabled",
    )

    conversation = create_conversation(
        db_session,
        user=user,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        False,
    )

    def fail_retrieve(**kwargs):
        raise AssertionError(
            "Memory retrieval must not run"
        )

    monkeypatch.setattr(
        chat_module,
        "retrieve_memories_for_user",
        fail_retrieve,
    )

    provider = CapturingProvider()

    result = generate_normal_chat_reply(
        db=db_session,
        conversation=conversation,
        message="Hello",
        provider=provider,
    )

    payload = json.loads(
        provider.input_text
    )

    assert payload[
        "personal_memory_context"
    ] == []

    assert result.citations == ()


def test_memory_retrieval_failure_falls_back(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="normal-memory-fallback",
    )

    conversation = create_conversation(
        db_session,
        user=user,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        True,
    )

    def fail_retrieve(**kwargs):
        raise RuntimeError(
            "simulated memory retrieval failure"
        )

    monkeypatch.setattr(
        chat_module,
        "retrieve_memories_for_user",
        fail_retrieve,
    )

    provider = CapturingProvider()

    result = generate_normal_chat_reply(
        db=db_session,
        conversation=conversation,
        message="Continue normally",
        provider=provider,
    )

    payload = json.loads(
        provider.input_text
    )

    assert payload[
        "personal_memory_context"
    ] == []

    assert result.content == (
        "Memory-aware response."
    )
    assert result.citations == ()


def test_current_message_precedence_is_in_prompt(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(
        db_session,
        suffix="normal-memory-precedence",
    )

    conversation = create_conversation(
        db_session,
        user=user,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        chat_module,
        "retrieve_memories_for_user",
        lambda **kwargs: [
            memory_hit(
                content="I prefer Java."
            )
        ],
    )

    provider = CapturingProvider()

    generate_normal_chat_reply(
        db=db_session,
        conversation=conversation,
        message="I now prefer Python.",
        provider=provider,
    )

    assert (
        "current user message is authoritative"
        in provider.instructions.lower()
    )

    assert (
        "not document evidence"
        in provider.instructions.lower()
    )
