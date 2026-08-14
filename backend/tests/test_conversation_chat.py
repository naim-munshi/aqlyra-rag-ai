import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.services.chat_service as chat_module

from app.api.dependencies import get_current_user
from app.llms import (
    LLMGeneration,
    LLMProviderInfo,
)
from app.main import app
from app.models.document_chunk import DocumentChunk
from app.models.user import User


class FakeNormalProvider:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="fake-normal",
            model_name="fake-chat-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        assert "document citations" in instructions

        self.inputs.append(
            input_text
        )

        return LLMGeneration(
            text="Normal assistant response.",
            provider_name="fake-normal",
            model_name="fake-chat-v1",
            response_id="normal-response-1",
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
    *,
    mode: str,
) -> str:
    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Chat test",
            "mode": mode,
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_normal_chat_persists_turn_without_citations(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="normal-chat",
    )

    authenticate_as(user)

    provider = FakeNormalProvider()

    monkeypatch.setattr(
        chat_module,
        "create_configured_llm_provider",
        lambda: provider,
    )

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Hello Aqlyra",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["mode"] == "normal"

    assert (
        payload["user_message"]["role"]
        == "user"
    )

    assistant = payload[
        "assistant_message"
    ]

    assert assistant["role"] == "assistant"
    assert assistant["mode"] == "normal"

    assert assistant["content"] == (
        "Normal assistant response."
    )

    assert assistant["citations"] == []

    assert assistant["provider_name"] == (
        "fake-normal"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200

    messages = history.json()

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_normal_chat_receives_previous_history(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="history-chat",
    )

    authenticate_as(user)

    provider = FakeNormalProvider()

    monkeypatch.setattr(
        chat_module,
        "create_configured_llm_provider",
        lambda: provider,
    )

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    first = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "My project is Aqlyra.",
        },
    )

    assert first.status_code == 200

    second = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "What is my project?",
        },
    )

    assert second.status_code == 200
    assert len(provider.inputs) == 2

    second_input = json.loads(
        provider.inputs[1]
    )

    history = second_input[
        "conversation_history"
    ]

    assert len(history) == 2

    assert history[0] == {
        "role": "user",
        "content": "My project is Aqlyra.",
    }

    assert history[1] == {
        "role": "assistant",
        "content": "Normal assistant response.",
    }

    assert second_input[
        "current_user_message"
    ] == "What is my project?"


def test_knowledge_chat_routes_through_rag(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="knowledge-chat",
    )

    authenticate_as(user)

    captured = {}

    source = SimpleNamespace(
        source_id="S1",
        chunk_id="chunk-1",
        document_id="doc-1",
        parent_chunk_id=None,
        original_filename="policy.md",
        chunk_role="content",
        chunk_level=0,
        chunk_index=0,
        source_label="Policy",
        section_path=("Security",),
        start_page=None,
        end_page=None,
        similarity_score=0.95,
        content="Grounded evidence.",
        was_truncated=False,
    )

    def fake_answer_question(
        **kwargs,
    ):
        captured.update(kwargs)

        return SimpleNamespace(
            answer_text=(
                "Grounded answer [S1]."
            ),
            provider_name="fake-rag",
            model_name="fake-rag-v1",
            response_id="rag-response-1",
            citations=(source,),
            is_refusal=False,
            input_tokens=20,
            output_tokens=8,
            total_tokens=28,
            evidence_tokens=12,
        )

    monkeypatch.setattr(
        chat_module,
        "answer_question",
        fake_answer_question,
    )

    conversation_id = create_conversation(
        client,
        mode="knowledge",
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "What does the policy say?",
            "document_ids": ["doc-1"],
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["mode"] == "knowledge"

    assistant = payload[
        "assistant_message"
    ]

    assert assistant["citations"][0][
        "source_id"
    ] == "S1"

    assert assistant["citations"][0][
        "document_id"
    ] == "doc-1"

    assert captured["user_id"] == user.id

    assert captured["document_ids"] == (
        "doc-1",
    )

    assert captured["top_k"] == 5


def test_other_user_cannot_send_message(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    owner = create_user(
        db_session,
        suffix="chat-owner",
    )

    other = create_user(
        db_session,
        suffix="chat-other",
    )

    authenticate_as(owner)

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    authenticate_as(other)

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Unauthorized message",
        },
    )

    assert response.status_code == 404


def test_generation_failure_persists_no_partial_turn(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="failed-chat",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    def fail_execution(**kwargs):
        raise RuntimeError(
            "generation failed"
        )

    monkeypatch.setattr(
        "app.api.conversations.execute_chat_turn",
        fail_execution,
    )

    try:
        client.post(
            (
                "/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            json={
                "content": "This should fail",
            },
        )
    except RuntimeError:
        pass

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_chat_validation_failure_returns_422_and_persists_nothing(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    from app.services.chat_service import (
        ChatValidationError,
    )

    user = create_user(
        db_session,
        suffix="chat-validation-failure",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    def fail_execution(**kwargs):
        raise ChatValidationError(
            "invalid chat request"
        )

    monkeypatch.setattr(
        "app.api.conversations.execute_chat_turn",
        fail_execution,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Hello",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "invalid chat request"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_provider_request_failure_returns_503_and_persists_nothing(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    from app.llms import (
        LLMProviderRequestError,
    )

    user = create_user(
        db_session,
        suffix="provider-request-failure",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    def fail_execution(**kwargs):
        raise LLMProviderRequestError(
            "provider unavailable"
        )

    monkeypatch.setattr(
        "app.api.conversations.execute_chat_turn",
        fail_execution,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Hello",
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "Conversation provider service "
        "is unavailable"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_provider_response_failure_returns_502_and_persists_nothing(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    from app.llms import (
        LLMProviderResponseError,
    )

    user = create_user(
        db_session,
        suffix="provider-response-failure",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    def fail_execution(**kwargs):
        raise LLMProviderResponseError(
            "invalid provider response"
        )

    monkeypatch.setattr(
        "app.api.conversations.execute_chat_turn",
        fail_execution,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Hello",
        },
    )

    assert response.status_code == 502

    assert response.json()["detail"] == (
        "The generated conversation answer "
        "failed validation"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_retrieval_validation_failure_returns_422_and_persists_nothing(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    from app.retrieval import (
        RetrievalValidationError,
    )

    user = create_user(
        db_session,
        suffix="retrieval-validation-failure",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="knowledge",
    )

    def fail_execution(**kwargs):
        raise RetrievalValidationError(
            "invalid retrieval request"
        )

    monkeypatch.setattr(
        "app.api.conversations.execute_chat_turn",
        fail_execution,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Find the answer",
        },
    )

    assert response.status_code == 422

    assert response.json()["detail"] == (
        "invalid retrieval request"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_normal_chat_rejects_document_selection(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="normal-document-boundary",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="normal",
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use this document",
            "document_ids": ["document-1"],
        },
    )

    assert response.status_code == 422

    assert response.json()["detail"] == (
        "Document selection is only "
        "supported in knowledge mode"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_real_knowledge_chat_persists_grounded_citation(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="real-knowledge-chat",
    )

    authenticate_as(user)

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "knowledge-policy.md",
                (
                    "# Security Policy\n\n"
                    "JWT bearer tokens protect "
                    "private API routes."
                ).encode("utf-8"),
                "text/markdown",
            ),
        },
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    process_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        )
    )

    assert process_response.status_code == 200

    chunk = db_session.scalar(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id,
            DocumentChunk.chunk_role
            == "content",
        )
        .order_by(
            DocumentChunk.chunk_index.asc()
        )
    )

    assert chunk is not None

    conversation_id = create_conversation(
        client,
        mode="knowledge",
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": chunk.embedding_content,
            "document_ids": [document_id],
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assistant = payload[
        "assistant_message"
    ]

    assert assistant["mode"] == "knowledge"

    assert assistant["content"] == (
        "Deterministic grounded answer [S1]."
    )

    assert len(
        assistant["citations"]
    ) == 1

    citation = assistant["citations"][0]

    assert citation["source_id"] == "S1"

    assert citation["document_id"] == (
        document_id
    )

    assert citation["filename"] == (
        "knowledge-policy.md"
    )

    history_response = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 2

    assert history[1]["citations"][0][
        "document_id"
    ] == document_id
