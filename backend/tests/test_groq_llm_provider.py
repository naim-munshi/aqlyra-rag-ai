from typing import Any

from app.llms.registry import (
    create_llm_provider,
)


class FakeResponses:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            dict[str, Any]
        ] = []

    def create(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(kwargs)

        return {
            "id": "groq-response-1",
            "output_text": (
                "A grounded answer [S1]."
            ),
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        }


class FakeClient:
    def __init__(
        self,
    ) -> None:
        self.responses = (
            FakeResponses()
        )


def test_groq_provider_generation(
) -> None:
    client = FakeClient()

    provider = create_llm_provider(
        provider_name="groq",
        model_name=(
            "openai/gpt-oss-20b"
        ),
        client=client,
    )

    generation = provider.generate(
        instructions=(
            "Answer from evidence."
        ),
        input_text=(
            "Question and evidence."
        ),
    )

    assert (
        provider.info.provider_name
        == "groq"
    )

    assert (
        provider.info.model_name
        == "openai/gpt-oss-20b"
    )

    assert generation.text == (
        "A grounded answer [S1]."
    )

    assert (
        generation.provider_name
        == "groq"
    )

    assert (
        generation.input_tokens
        == 100
    )

    assert (
        generation.output_tokens
        == 20
    )

    assert (
        generation.total_tokens
        == 120
    )

    assert len(
        client.responses.calls
    ) == 1

    request = (
        client.responses.calls[0]
    )

    assert request["model"] == (
        "openai/gpt-oss-20b"
    )

    assert "store" not in request