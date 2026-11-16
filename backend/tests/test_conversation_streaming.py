import json
from types import SimpleNamespace

import app.api.conversations as conversation_module

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.services.chat_service as chat_module

from app.api.dependencies import (
    get_current_user,
)
from app.llms.types import (
    LLMGeneration,
    LLMProviderInfo,
    LLMProviderRequestError,
    LLMStreamEvent,
)
from app.main import app
from app.models.user import User


class SuccessfulStreamingProvider:
    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="stream-http-test",
            model_name="stream-http-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        raise AssertionError(
            "Streaming endpoint must "
            "not call generate()"
        )

    def stream(
        self,
        *,
        instructions: str,
        input_text: str,
    ):
        yield LLMStreamEvent(
            event_type="delta",
            delta_text="Hello",
        )

        yield LLMStreamEvent(
            event_type="delta",
            delta_text=" from Aqlyra",
        )

        yield LLMStreamEvent(
            event_type="complete",
            generation=LLMGeneration(
                text="Hello from Aqlyra",
                provider_name=(
                    "stream-http-test"
                ),
                model_name="stream-http-v1",
                response_id="stream-http-1",
                input_tokens=10,
                output_tokens=4,
                total_tokens=14,
            ),
        )


class FailingStreamingProvider:
    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="stream-fail-test",
            model_name="stream-fail-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        raise AssertionError(
            "Streaming endpoint must "
            "not call generate()"
        )

    def stream(
        self,
        *,
        instructions: str,
        input_text: str,
    ):
        yield LLMStreamEvent(
            event_type="delta",
            delta_text="Partial answer",
        )

        raise LLMProviderRequestError(
            "simulated stream failure"
        )


def create_user(
    db: Session,
    *,
    suffix: str,
) -> User:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        hashed_password=(
            "test-password-hash"
        ),
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
            "title": "Streaming test",
            "mode": mode,
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def parse_sse(
    body: str,
) -> list[dict]:
    events: list[dict] = []
    current: dict = {}

    for line in body.splitlines():
        if line.startswith("event: "):
            current["event"] = (
                line.removeprefix(
                    "event: "
                )
            )

        elif line.startswith("data: "):
            current["data"] = json.loads(
                line.removeprefix(
                    "data: "
                )
            )

        elif not line and current:
            events.append(current)
            current = {}

    if current:
        events.append(current)

    return events


def test_normal_conversation_streams_and_persists(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="stream-http-success",
    )

    authenticate_as(user)

    provider = SuccessfulStreamingProvider()

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
            f"{conversation_id}/messages/stream"
        ),
        json={
            "content": "Hello",
        },
    )

    assert response.status_code == 200

    assert (
        response.headers["content-type"]
        .startswith("text/event-stream")
    )

    events = parse_sse(
        response.text
    )

    assert [
        event["event"]
        for event in events
    ] == [
        "start",
        "delta",
        "delta",
        "complete",
    ]

    assert (
        events[1]["data"]["text"]
        == "Hello"
    )

    assert (
        events[2]["data"]["text"]
        == " from Aqlyra"
    )

    complete = events[-1]["data"]

    assert (
        complete["conversation_id"]
        == conversation_id
    )

    assert complete["mode"] == "normal"

    assistant = complete[
        "assistant_message"
    ]

    assert (
        assistant["content"]
        == "Hello from Aqlyra"
    )

    assert assistant["citations"] == []

    assert assistant["provider_name"] == (
        "stream-http-test"
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

    assert (
        messages[1]["content"]
        == "Hello from Aqlyra"
    )


def test_stream_failure_persists_no_partial_turn(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="stream-http-failure",
    )

    authenticate_as(user)

    provider = FailingStreamingProvider()

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
            f"{conversation_id}/messages/stream"
        ),
        json={
            "content": "Fail please",
        },
    )

    assert response.status_code == 200

    events = parse_sse(
        response.text
    )

    assert [
        event["event"]
        for event in events
    ] == [
        "start",
        "delta",
        "error",
    ]

    error = events[-1]["data"]

    assert error["status"] == 503

    assert error["code"] == (
        "provider_unavailable"
    )

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_stream_rejects_knowledge_mode_for_now(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="stream-knowledge",
    )

    authenticate_as(user)

    conversation_id = create_conversation(
        client,
        mode="knowledge",
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages/stream"
        ),
        json={
            "content": "Use my document",
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == (
        "Streaming currently supports "
        "normal conversations only"
    )


def test_stream_first_delta_metrics_distinguish_normal_and_verified_full_paths(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    user = create_user(db_session, suffix="stream-timing-labels")
    authenticate_as(user)
    events_logged: list[tuple[str, dict]] = []

    class Recorder:
        def info(self, event, **fields):
            events_logged.append((event, fields))

    monkeypatch.setattr(conversation_module, "app_logger", Recorder())
    monkeypatch.setattr(
        chat_module, "create_configured_llm_provider",
        lambda: SuccessfulStreamingProvider(),
    )
    cid = create_conversation(client, mode="normal")
    response = client.post(
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"content": "Synthetic greeting", "web_mode": "off"},
    )
    assert response.status_code == 200
    assert [event["event"] for event in parse_sse(response.text)] == [
        "start", "delta", "delta", "complete",
    ]
    first = [
        values for event, values in events_logged
        if event == "chat_stream_first_delta"
    ]
    assert len(first) == 1
    assert first[0]["path_type"] == "normal_model_delta"
    assert first[0]["elapsed_ms"] >= 0

    # The evidence/web path must emit one complete, validated result; this
    # is not a model-token stream and must be measured in a different bucket.
    events_logged.clear()
    monkeypatch.setattr(
        conversation_module, "resolve_public_research_followup",
        lambda **kwargs: kwargs["message"],
    )
    monkeypatch.setattr(
        conversation_module, "route_web_request",
        lambda *args: "on",
    )
    monkeypatch.setattr(
        conversation_module, "execute_chat_turn",
        lambda **kwargs: SimpleNamespace(
            content="Synthetic evidence-verified result",
            mode="normal",
            provider_name="synthetic",
            model_name="synthetic-research",
            response_id="safe-1",
            citations=(),
            is_refusal=False,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            evidence_tokens=0,
        ),
    )
    monkeypatch.setattr(
        conversation_module, "extract_memories_best_effort",
        lambda **kwargs: None,
    )
    cid = create_conversation(client, mode="normal")
    response = client.post(
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"content": "Synthetic question", "web_mode": "on"},
    )
    assert response.status_code == 200
    web_events = parse_sse(response.text)
    assert [event["event"] for event in web_events] == [
        "start", "tool_status", "delta", "complete",
    ]
    assert web_events[2]["data"]["text"] == "Synthetic evidence-verified result"
    first = [
        values for event, values in events_logged
        if event == "chat_stream_first_delta"
    ]
    assert len(first) == 1
    assert first[0]["path_type"] == "validated_full_answer"
    assert first[0]["elapsed_ms"] >= 0
    # Backend counters must never log the answer, user, or conversation ID.
    assert not any(
        "Synthetic evidence-verified result" in str(fields)
        or cid in str(fields)
        for _, fields in events_logged
    )
