import pytest

from app.llms import (
    DeterministicLLMProvider,
    LLMValidationError,
    create_llm_provider,
)


def test_registry_creates_deterministic_provider(
) -> None:
    provider = create_llm_provider(
        provider_name="deterministic",
        deterministic_response=(
            "Known test answer."
        ),
    )

    assert isinstance(
        provider,
        DeterministicLLMProvider,
    )

    result = provider.generate(
        instructions="Use evidence only.",
        input_text="Question and context",
    )

    assert result.text == (
        "Known test answer."
    )

    assert result.provider_name == (
        "deterministic"
    )

    assert result.model_name == (
        "deterministic-rag-v1"
    )


def test_registry_rejects_unknown_provider(
) -> None:
    with pytest.raises(
        LLMValidationError
    ):
        create_llm_provider(
            provider_name="unknown",
        )
