import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.services.chat_service as chat_module
import app.services.memory_extraction_service as extraction_module

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.llms import (
    LLMGeneration,
    LLMProviderInfo,
)
from app.main import app
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.user import User


class CapturingChatProvider:
    def __init__(self) -> None:
        self.inputs: list[dict] = []

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="memory-e2e-chat",
            model_name="memory-e2e-chat-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        self.inputs.append(
            json.loads(input_text)
        )

        return LLMGeneration(
            text=(
                "Normal memory integration "
                "response."
            ),
            provider_name="memory-e2e-chat",
            model_name="memory-e2e-chat-v1",
            response_id=(
                f"memory-e2e-response-"
                f"{len(self.inputs)}"
            ),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )


class SequentialExtractionProvider:
    def __init__(
        self,
        payloads: list[dict],
    ) -> None:
        self.payloads = payloads
        self.calls = 0

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="memory-e2e-extractor",
            model_name="memory-e2e-extractor-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        if self.calls >= len(
            self.payloads
        ):
            raise AssertionError(
                "Unexpected memory extraction call"
            )

        payload = self.payloads[
            self.calls
        ]

        self.calls += 1

        return LLMGeneration(
            text=json.dumps(
                payload,
                ensure_ascii=False,
            ),
            provider_name=(
                "memory-e2e-extractor"
            ),
            model_name=(
                "memory-e2e-extractor-v1"
            ),
            response_id=(
                f"memory-extraction-"
                f"{self.calls}"
            ),
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


def authenticate_as(
    user: User,
) -> None:
    app.dependency_overrides[
        get_current_user
    ] = lambda: user


def create_conversation(
    client: TestClient,
) -> str:
    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Memory integration",
            "mode": "normal",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def post_message(
    client: TestClient,
    *,
    conversation_id: str,
    content: str,
) -> dict:
    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": content,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload[
        "assistant_message"
    ]["citations"] == []

    return payload


def memories_for_user(
    db: Session,
    *,
    user_id: str,
) -> list[Memory]:
    return list(
        db.scalars(
            select(Memory)
            .where(
                Memory.user_id == user_id
            )
            .order_by(Memory.id)
        ).all()
    )


def embeddings_for_memory(
    db: Session,
    *,
    memory_id: str,
) -> list[MemoryEmbedding]:
    return list(
        db.scalars(
            select(MemoryEmbedding).where(
                MemoryEmbedding.memory_id
                == memory_id
            )
        ).all()
    )


def enable_memory_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "MEMORY_AUTO_EXTRACT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_TOP_K",
        5,
    )

    # Exact deterministic embedding matches
    # score 1.0, making the integration test
    # deterministic without external APIs.
    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_MIN_SIMILARITY",
        0.99,
    )


def install_providers(
    *,
    monkeypatch: pytest.MonkeyPatch,
    chat_provider: CapturingChatProvider,
    extraction_provider: (
        SequentialExtractionProvider
    ),
) -> None:
    monkeypatch.setattr(
        chat_module,
        "create_configured_llm_provider",
        lambda: chat_provider,
    )

    monkeypatch.setattr(
        extraction_module,
        "create_configured_llm_provider",
        lambda: extraction_provider,
    )


def test_memory_lifecycle_from_chat_to_later_chat(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_memory_pipeline(
        monkeypatch
    )

    chat_provider = (
        CapturingChatProvider()
    )

    extraction_provider = (
        SequentialExtractionProvider(
            [
                {
                    "memories": [
                        {
                            "kind": (
                                "preference"
                            ),
                            "content": (
                                "I prefer Python."
                            ),
                            "importance": 0.8,
                            "confidence": 0.95,
                        }
                    ],
                    "retirements": [],
                },
                {
                    "memories": [],
                    "retirements": [],
                },
            ]
        )
    )

    install_providers(
        monkeypatch=monkeypatch,
        chat_provider=chat_provider,
        extraction_provider=(
            extraction_provider
        ),
    )

    user = create_user(
        db_session,
        suffix="memory-e2e-lifecycle",
    )

    authenticate_as(user)

    conversation_id = (
        create_conversation(client)
    )

    first = post_message(
        client,
        conversation_id=conversation_id,
        content="I prefer Python.",
    )

    memories = memories_for_user(
        db_session,
        user_id=str(user.id),
    )

    assert len(memories) == 1

    memory = memories[0]

    assert memory.kind == "preference"
    assert memory.content == (
        "I prefer Python."
    )
    assert memory.is_active is True
    assert memory.source_message_id == (
        first["user_message"]["id"]
    )

    embeddings = (
        embeddings_for_memory(
            db_session,
            memory_id=memory.id,
        )
    )

    assert len(embeddings) == 1

    memory_id = memory.id
    embedding_id = embeddings[0].id

    second = post_message(
        client,
        conversation_id=conversation_id,
        content="I prefer Python.",
    )

    assert second[
        "assistant_message"
    ]["citations"] == []

    assert len(chat_provider.inputs) == 2

    assert chat_provider.inputs[0][
        "personal_memory_context"
    ] == []

    assert chat_provider.inputs[1][
        "personal_memory_context"
    ] == [
        {
            "kind": "preference",
            "content": "I prefer Python.",
        }
    ]

    delete_response = client.delete(
        (
            "/api/v1/conversations/"
            f"{conversation_id}"
        )
    )

    assert (
        delete_response.status_code
        == 204
    )

    db_session.expire_all()

    persisted_memory = db_session.scalar(
        select(Memory).where(
            Memory.id == memory_id
        )
    )

    assert persisted_memory is not None

    # Conversation/message history may disappear,
    # but Aqlyra-owned long-term memory survives.
    assert (
        persisted_memory.source_message_id
        is None
    )

    persisted_embedding = (
        db_session.scalar(
            select(
                MemoryEmbedding
            ).where(
                MemoryEmbedding.id
                == embedding_id
            )
        )
    )

    assert persisted_embedding is not None

    # User deletion owns the full personal-memory
    # lifecycle and must cascade both layers.
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
            select(
                MemoryEmbedding
            ).where(
                MemoryEmbedding.id
                == embedding_id
            )
        )
        is None
    )


def test_chat_extraction_deduplicates_across_turns(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "MEMORY_AUTO_EXTRACT_ENABLED",
        True,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        False,
    )

    chat_provider = (
        CapturingChatProvider()
    )

    extraction_provider = (
        SequentialExtractionProvider(
            [
                {
                    "memories": [
                        {
                            "kind": (
                                "preference"
                            ),
                            "content": (
                                "I prefer Python."
                            ),
                            "importance": 0.6,
                            "confidence": 0.80,
                        }
                    ],
                    "retirements": [],
                },
                {
                    "memories": [
                        {
                            "kind": (
                                "preference"
                            ),
                            "content": (
                                "I prefer Python."
                            ),
                            "importance": 0.9,
                            "confidence": 0.96,
                        }
                    ],
                    "retirements": [],
                },
            ]
        )
    )

    install_providers(
        monkeypatch=monkeypatch,
        chat_provider=chat_provider,
        extraction_provider=(
            extraction_provider
        ),
    )

    user = create_user(
        db_session,
        suffix="memory-e2e-dedupe",
    )

    authenticate_as(user)

    conversation_id = (
        create_conversation(client)
    )

    first = post_message(
        client,
        conversation_id=conversation_id,
        content="I prefer Python.",
    )

    post_message(
        client,
        conversation_id=conversation_id,
        content="I prefer Python.",
    )

    memories = memories_for_user(
        db_session,
        user_id=str(user.id),
    )

    assert len(memories) == 1

    memory = memories[0]

    assert memory.is_active is True
    assert memory.importance == 0.9
    assert memory.confidence == 0.96

    # Reconciliation preserves original
    # provenance rather than rewriting history.
    assert memory.source_message_id == (
        first["user_message"]["id"]
    )

    embeddings = (
        embeddings_for_memory(
            db_session,
            memory_id=memory.id,
        )
    )

    assert len(embeddings) == 1
    assert extraction_provider.calls == 2


def test_explicit_retirement_removes_memory_from_future_chat(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_memory_pipeline(
        monkeypatch
    )

    chat_provider = (
        CapturingChatProvider()
    )

    extraction_provider = (
        SequentialExtractionProvider(
            [
                {
                    "memories": [
                        {
                            "kind": (
                                "preference"
                            ),
                            "content": (
                                "I prefer Java."
                            ),
                            "importance": 0.8,
                            "confidence": 0.95,
                        }
                    ],
                    "retirements": [],
                },
                {
                    "memories": [],
                    "retirements": [
                        {
                            "kind": (
                                "preference"
                            ),
                            "content": (
                                "I prefer Java."
                            ),
                            "confidence": 0.99,
                        }
                    ],
                },
                {
                    "memories": [],
                    "retirements": [],
                },
            ]
        )
    )

    install_providers(
        monkeypatch=monkeypatch,
        chat_provider=chat_provider,
        extraction_provider=(
            extraction_provider
        ),
    )

    user = create_user(
        db_session,
        suffix="memory-e2e-retirement",
    )

    authenticate_as(user)

    conversation_id = (
        create_conversation(client)
    )

    post_message(
        client,
        conversation_id=conversation_id,
        content="I prefer Java.",
    )

    memories = memories_for_user(
        db_session,
        user_id=str(user.id),
    )

    assert len(memories) == 1

    memory_id = memories[0].id

    post_message(
        client,
        conversation_id=conversation_id,
        content="I no longer prefer Java.",
    )

    db_session.expire_all()

    memory = db_session.scalar(
        select(Memory).where(
            Memory.id == memory_id
        )
    )

    assert memory is not None
    assert memory.is_active is False

    # The vector may remain as a replaceable
    # index, but inactive memories must never
    # enter future LLM context.
    assert len(
        embeddings_for_memory(
            db_session,
            memory_id=memory_id,
        )
    ) == 1

    third = post_message(
        client,
        conversation_id=conversation_id,
        content="I prefer Java.",
    )

    assert third[
        "assistant_message"
    ]["citations"] == []

    assert len(chat_provider.inputs) == 3

    assert chat_provider.inputs[2][
        "personal_memory_context"
    ] == []


def test_normal_chat_memory_isolated_between_users(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_memory_pipeline(
        monkeypatch
    )

    chat_provider = (
        CapturingChatProvider()
    )

    extraction_provider = (
        SequentialExtractionProvider(
            [
                {
                    "memories": [
                        {
                            "kind": (
                                "preference"
                            ),
                            "content": (
                                "I prefer Python."
                            ),
                            "importance": 0.8,
                            "confidence": 0.95,
                        }
                    ],
                    "retirements": [],
                },
                {
                    "memories": [],
                    "retirements": [],
                },
            ]
        )
    )

    install_providers(
        monkeypatch=monkeypatch,
        chat_provider=chat_provider,
        extraction_provider=(
            extraction_provider
        ),
    )

    owner = create_user(
        db_session,
        suffix="memory-e2e-owner",
    )

    other = create_user(
        db_session,
        suffix="memory-e2e-other",
    )

    authenticate_as(owner)

    owner_conversation = (
        create_conversation(client)
    )

    post_message(
        client,
        conversation_id=(
            owner_conversation
        ),
        content="I prefer Python.",
    )

    owner_memories = memories_for_user(
        db_session,
        user_id=str(owner.id),
    )

    assert len(owner_memories) == 1

    authenticate_as(other)

    other_conversation = (
        create_conversation(client)
    )

    response = post_message(
        client,
        conversation_id=(
            other_conversation
        ),
        content="I prefer Python.",
    )

    assert response[
        "assistant_message"
    ]["citations"] == []

    # First input belongs to owner before memory
    # existed. Second belongs to another user and
    # must not receive owner's stored memory.
    assert len(chat_provider.inputs) == 2

    assert chat_provider.inputs[1][
        "personal_memory_context"
    ] == []

    assert memories_for_user(
        db_session,
        user_id=str(other.id),
    ) == []

    db_session.expire_all()

    owner_memory = db_session.scalar(
        select(Memory).where(
            Memory.id
            == owner_memories[0].id
        )
    )

    assert owner_memory is not None
    assert owner_memory.is_active is True
