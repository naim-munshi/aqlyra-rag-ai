import json

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.llms.types import (
    LLMGeneration,
    LLMProviderInfo,
    LLMStreamEvent,
)
from app.models.conversation import Conversation
from app.models.user import User
from app.services.chat_service import (
    stream_normal_chat_reply,
)


class StreamingProvider:
    def __init__(self) -> None:
        self.instructions: str | None = None
        self.input_text: str | None = None

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="stream-test",
            model_name="stream-test-v1",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        raise AssertionError(
            "Streaming path must not call generate()"
        )

    def stream(
        self,
        *,
        instructions: str,
        input_text: str,
    ):
        self.instructions = instructions
        self.input_text = input_text

        yield LLMStreamEvent(
            event_type="delta",
            delta_text="Hello",
        )

        yield LLMStreamEvent(
            event_type="delta",
            delta_text=" Aqlyra",
        )

        yield LLMStreamEvent(
            event_type="complete",
            generation=LLMGeneration(
                text="Hello Aqlyra",
                provider_name="stream-test",
                model_name="stream-test-v1",
                response_id="stream-response-1",
                input_tokens=10,
                output_tokens=3,
                total_tokens=13,
            ),
        )


def create_user(
    db: Session,
) -> User:
    user = User(
        email="stream-service@example.com",
        username="stream-service",
        hashed_password="test-password-hash",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_conversation(
    db: Session,
    user: User,
) -> Conversation:
    conversation = Conversation(
        user_id=str(user.id),
        title="Streaming chat",
        mode="normal",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def test_normal_chat_stream_uses_provider_stream(
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(db_session)

    conversation = create_conversation(
        db_session,
        user,
    )

    monkeypatch.setattr(
        settings,
        "MEMORY_CHAT_ENABLED",
        False,
    )

    provider = StreamingProvider()

    events = list(
        stream_normal_chat_reply(
            db=db_session,
            conversation=conversation,
            message="Hello",
            provider=provider,
        )
    )

    assert [
        event.delta_text
        for event in events
        if event.event_type == "delta"
    ] == [
        "Hello",
        " Aqlyra",
    ]

    complete = events[-1]

    assert complete.event_type == "complete"
    assert complete.generation is not None
    assert (
        complete.generation.text
        == "Hello Aqlyra"
    )

    payload = json.loads(
        provider.input_text
    )

    assert payload[
        "current_user_message"
    ] == "Hello"

    assert payload[
        "personal_memory_context"
    ] == []

    assert (
        "document citations"
        in provider.instructions
    )
