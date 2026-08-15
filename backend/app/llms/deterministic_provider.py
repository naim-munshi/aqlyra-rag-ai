from collections.abc import Iterator

from app.llms.types import (
    LLMGeneration,
    LLMProviderInfo,
    LLMStreamEvent,
    LLMValidationError,
)


DEFAULT_DETERMINISTIC_RESPONSE = (
    "Deterministic grounded answer [S1]."
)


class DeterministicLLMProvider:
    """
    Predictable provider for tests and local pipeline checks.

    This provider does not perform language-model reasoning.
    """

    def __init__(
        self,
        *,
        response_text: str = (
            DEFAULT_DETERMINISTIC_RESPONSE
        ),
        max_output_tokens: int = 800,
    ) -> None:
        cleaned_response = (
            response_text.strip()
        )

        if not cleaned_response:
            raise LLMValidationError(
                "Deterministic response text "
                "cannot be empty"
            )

        if max_output_tokens < 1:
            raise LLMValidationError(
                "max_output_tokens must be positive"
            )

        self._response_text = (
            cleaned_response
        )

        self._info = LLMProviderInfo(
            provider_name="deterministic",
            model_name=(
                "deterministic-rag-v1"
            ),
            max_output_tokens=(
                max_output_tokens
            ),
        )

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        if not instructions.strip():
            raise LLMValidationError(
                "LLM instructions cannot be empty"
            )

        if not input_text.strip():
            raise LLMValidationError(
                "LLM input cannot be empty"
            )

        return LLMGeneration(
            text=self._response_text,
            provider_name=(
                self.info.provider_name
            ),
            model_name=(
                self.info.model_name
            ),
        )

    def stream(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> Iterator[LLMStreamEvent]:
        generation = self.generate(
            instructions=instructions,
            input_text=input_text,
        )

        yield LLMStreamEvent(
            event_type="delta",
            delta_text=generation.text,
        )

        yield LLMStreamEvent(
            event_type="complete",
            generation=generation,
        )
