from types import SimpleNamespace
from typing import Any

import pytest

from app.llms import (
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMValidationError,
    OpenAILLMProvider,
)


class FakeResponsesResource:
    def __init__(
        self,
        *,
        response: Any = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[
            dict[str, Any]
        ] = []

    def create(
        self,
        **kwargs: Any,
    ) -> Any:
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.response


class FakeOpenAIClient:
    def __init__(
        self,
        responses: FakeResponsesResource,
    ) -> None:
        self.responses = responses


def test_openai_llm_provider_exposes_config(
) -> None:
    resource = FakeResponsesResource(
        response=SimpleNamespace(
            id="response-1",
            output_text="Answer",
            usage=None,
        )
    )

    provider = OpenAILLMProvider(
        api_key="",
        model="test-model",
        max_output_tokens=500,
        client=FakeOpenAIClient(resource),
    )

    assert (
        provider.info.provider_name
        == "openai"
    )

    assert (
        provider.info.model_name
        == "test-model"
    )

    assert (
        provider.info.max_output_tokens
        == 500
    )


def test_openai_llm_provider_uses_responses_api(
) -> None:
    response = SimpleNamespace(
        id="response-123",
        output_text="Grounded answer [S1].",
        usage=SimpleNamespace(
            input_tokens=120,
            output_tokens=30,
            total_tokens=150,
        ),
    )

    resource = FakeResponsesResource(
        response=response
    )

    provider = OpenAILLMProvider(
        api_key="",
        model="test-model",
        max_output_tokens=600,
        client=FakeOpenAIClient(resource),
    )

    result = provider.generate(
        instructions=(
            "Answer only from evidence."
        ),
        input_text=(
            "Question and evidence context"
        ),
    )

    assert len(resource.calls) == 1

    assert resource.calls[0] == {
        "model": "test-model",
        "instructions": (
            "Answer only from evidence."
        ),
        "input": (
            "Question and evidence context"
        ),
        "max_output_tokens": 600,
        "store": False,
    }

    assert result.text == (
        "Grounded answer [S1]."
    )

    assert result.response_id == (
        "response-123"
    )

    assert result.input_tokens == 120
    assert result.output_tokens == 30
    assert result.total_tokens == 150


def test_openai_llm_provider_reads_refusal(
) -> None:
    refusal_part = SimpleNamespace(
        type="refusal",
        refusal=(
            "The evidence is insufficient."
        ),
    )

    output_item = SimpleNamespace(
        content=[refusal_part]
    )

    resource = FakeResponsesResource(
        response=SimpleNamespace(
            id="response-refusal",
            output_text="",
            output=[output_item],
            usage=None,
        )
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeOpenAIClient(resource),
    )

    result = provider.generate(
        instructions="Use evidence only.",
        input_text="Question and context",
    )

    assert result.text == (
        "The evidence is insufficient."
    )


def test_openai_llm_provider_rejects_empty_output(
) -> None:
    resource = FakeResponsesResource(
        response=SimpleNamespace(
            id="response-empty",
            output_text="",
            output=[],
            usage=None,
        )
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeOpenAIClient(resource),
    )

    with pytest.raises(
        LLMProviderResponseError
    ):
        provider.generate(
            instructions="Use evidence only.",
            input_text="Question and context",
        )


def test_openai_llm_provider_wraps_request_error(
) -> None:
    resource = FakeResponsesResource(
        error=RuntimeError(
            "provider unavailable"
        )
    )

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeOpenAIClient(resource),
    )

    with pytest.raises(
        LLMProviderRequestError
    ):
        provider.generate(
            instructions="Use evidence only.",
            input_text="Question and context",
        )


def test_openai_llm_provider_requires_api_key(
) -> None:
    with pytest.raises(
        LLMValidationError
    ):
        OpenAILLMProvider(
            api_key="",
        )


def test_openai_llm_provider_sends_text_format(
) -> None:
    resource = FakeResponsesResource(
        response=SimpleNamespace(
            id="response-json",
            output_text='{"scores":[]}',
            usage=None,
        )
    )

    text_format = {
        "type": "json_schema",
        "name": "test_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "array",
                },
            },
            "required": ["scores"],
            "additionalProperties": False,
        },
    }

    provider = OpenAILLMProvider(
        api_key="",
        client=FakeOpenAIClient(resource),
        text_format=text_format,
    )

    provider.generate(
        instructions="Return structured JSON.",
        input_text="Test input",
    )

    assert (
        resource.calls[0]["text"]
        == {
            "format": text_format,
        }
    )
