from types import SimpleNamespace
from typing import Any

import pytest

from app.llms.openai_provider import (
    OpenAILLMProvider,
)
from app.llms.registry import (
    create_llm_provider,
)
from app.llms.types import (
    LLMProviderRequestError,
    LLMProviderResponseError,
)


class FakeStreamingResponses:
    def __init__(
        self,
        *,
        events: list[Any] | None = None,
        create_error: Exception | None = None,
        iteration_error: Exception | None = None,
    ) -> None:
        self.events = events or []
        self.create_error = create_error
        self.iteration_error = (
            iteration_error
        )
        self.calls: list[
            dict[str, Any]
        ] = []

    def create(
        self,
        **kwargs: Any,
    ) -> Any:
        self.calls.append(kwargs)

        if self.create_error is not None:
            raise self.create_error

        resource = self

        class FakeStream:
            def __iter__(self):
                for event in resource.events:
                    yield event

                if (
                    resource.iteration_error
                    is not None
                ):
                    raise (
                        resource.iteration_error
                    )

        return FakeStream()


class FakeClient:
    def __init__(
        self,
        responses: FakeStreamingResponses,
    ) -> None:
        self.responses = responses


def completed_event(
    *,
    text: str = "Hello world",
) -> Any:
    response = SimpleNamespace(
        id="response-stream-1",
        output_text=text,
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=2,
            total_tokens=12,
        ),
    )

    return SimpleNamespace(
        type="response.completed",
        response=response,
    )


def test_openai_stream_emits_deltas_and_completion():
    resource = FakeStreamingResponses(
        events=[
            SimpleNamespace(
                type=(
                    "response.output_text.delta"
                ),
                delta="Hello",
            ),
            SimpleNamespace(
                type=(
                    "response.output_text.delta"
                ),
                delta=" world",
            ),
            completed_event(),
        ]
    )

    provider = OpenAILLMProvider(
        api_key="",
        model="test-model",
        client=FakeClient(resource),
    )

    events = list(
        provider.stream(
            instructions="Answer clearly.",
            input_text="Say hello.",
        )
    )

    assert [
        event.delta_text
        for event in events
        if event.event_type == "delta"
    ] == [
        "Hello",
        " world",
    ]

    complete = events[-1]

    assert complete.event_type == "complete"
    assert complete.generation is not None

    generation = complete.generation

    assert generation.text == "Hello world"
    assert (
        generation.provider_name
        == "openai"
    )
    assert generation.model_name == (
        "test-model"
    )
    assert generation.response_id == (
        "response-stream-1"
    )
    assert generation.input_tokens == 10
    assert generation.output_tokens == 2
    assert generation.total_tokens == 12

    assert resource.calls == [
        {
            "model": "test-model",
            "instructions": (
                "Answer clearly."
            ),
            "input": "Say hello.",
            "max_output_tokens": 800,
            "stream": True,
            "store": False,
        }
    ]


def test_groq_inherits_native_streaming():
    resource = FakeStreamingResponses(
        events=[
            SimpleNamespace(
                type=(
                    "response.output_text.delta"
                ),
                delta="Fast",
            ),
            SimpleNamespace(
                type=(
                    "response.output_text.delta"
                ),
                delta=" answer",
            ),
            completed_event(
                text="Fast answer"
            ),
        ]
    )

    provider = create_llm_provider(
        provider_name="groq",
        model_name="openai/gpt-oss-20b",
        client=FakeClient(resource),
    )

    events = list(
        provider.stream(
            instructions="Answer.",
            input_text="Question.",
        )
    )

    assert (
        "".join(
            event.delta_text
            for event in events
            if event.event_type == "delta"
        )
        == "Fast answer"
    )

    complete = events[-1]

    assert complete.generation is not None
    assert (
        complete.generation.provider_name
        == "groq"
    )

    request = resource.calls[0]

    assert request["stream"] is True
    assert "store" not in request


def test_stream_normalizes_refusal_delta():
    resource = FakeStreamingResponses(
        events=[
            SimpleNamespace(
                type="response.refusal.delta",
                delta="I cannot answer.",
            ),
            completed_event(
                text="I cannot answer."
            ),
        ]
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeClient(resource),
    )

    events = list(
        provider.stream(
            instructions="Answer safely.",
            input_text="Question.",
        )
    )

    assert events[0].event_type == "delta"
    assert events[0].delta_text == (
        "I cannot answer."
    )


def test_stream_wraps_creation_error():
    resource = FakeStreamingResponses(
        create_error=RuntimeError(
            "provider unavailable"
        )
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeClient(resource),
    )

    with pytest.raises(
        LLMProviderRequestError
    ):
        list(
            provider.stream(
                instructions="Answer.",
                input_text="Question.",
            )
        )


def test_stream_wraps_iteration_error():
    resource = FakeStreamingResponses(
        events=[
            SimpleNamespace(
                type=(
                    "response.output_text.delta"
                ),
                delta="Partial",
            ),
        ],
        iteration_error=RuntimeError(
            "connection dropped"
        ),
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeClient(resource),
    )

    with pytest.raises(
        LLMProviderRequestError
    ):
        list(
            provider.stream(
                instructions="Answer.",
                input_text="Question.",
            )
        )


def test_stream_requires_completed_event():
    resource = FakeStreamingResponses(
        events=[
            SimpleNamespace(
                type=(
                    "response.output_text.delta"
                ),
                delta="Partial",
            ),
        ]
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeClient(resource),
    )

    with pytest.raises(
        LLMProviderResponseError
    ):
        list(
            provider.stream(
                instructions="Answer.",
                input_text="Question.",
            )
        )
