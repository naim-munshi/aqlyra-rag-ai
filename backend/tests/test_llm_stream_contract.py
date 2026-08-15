import pytest

from app.llms.deterministic_provider import (
    DeterministicLLMProvider,
)
from app.llms.types import (
    LLMValidationError,
)


def test_deterministic_stream_emits_delta_then_complete():
    provider = DeterministicLLMProvider(
        response_text="Hello Aqlyra",
    )

    events = list(
        provider.stream(
            instructions="Answer clearly.",
            input_text="Say hello.",
        )
    )

    assert len(events) == 2

    delta_event = events[0]

    assert delta_event.event_type == "delta"
    assert delta_event.delta_text == "Hello Aqlyra"
    assert delta_event.generation is None

    complete_event = events[1]

    assert complete_event.event_type == "complete"
    assert complete_event.delta_text == ""
    assert complete_event.generation is not None

    generation = complete_event.generation

    assert generation.text == "Hello Aqlyra"
    assert (
        generation.provider_name
        == "deterministic"
    )
    assert (
        generation.model_name
        == "deterministic-rag-v1"
    )


@pytest.mark.parametrize(
    (
        "instructions",
        "input_text",
    ),
    [
        ("", "question"),
        ("instructions", ""),
        ("   ", "question"),
        ("instructions", "   "),
    ],
)
def test_deterministic_stream_validates_input(
    instructions: str,
    input_text: str,
):
    provider = DeterministicLLMProvider()

    with pytest.raises(
        LLMValidationError
    ):
        list(
            provider.stream(
                instructions=instructions,
                input_text=input_text,
            )
        )


def test_stream_completion_matches_generate():
    provider = DeterministicLLMProvider(
        response_text="Stable response",
    )

    generated = provider.generate(
        instructions="Answer.",
        input_text="Question.",
    )

    events = list(
        provider.stream(
            instructions="Answer.",
            input_text="Question.",
        )
    )

    completed = events[-1].generation

    assert completed is not None
    assert completed == generated
