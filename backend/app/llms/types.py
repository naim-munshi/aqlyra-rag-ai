from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol


class LLMError(Exception):
    """Base exception for LLM provider failures."""


class LLMValidationError(LLMError):
    """Raised when LLM input or configuration is invalid."""


class LLMProviderRequestError(LLMError):
    """Raised when an external LLM request fails."""


class LLMProviderResponseError(LLMError):
    """Raised when an LLM response is invalid."""


@dataclass(frozen=True, slots=True)
class LLMProviderInfo:
    provider_name: str
    model_name: str
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class LLMGeneration:
    text: str
    provider_name: str
    model_name: str
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


LLMStreamEventType = Literal[
    "delta",
    "complete",
]


@dataclass(frozen=True, slots=True)
class LLMStreamEvent:
    event_type: LLMStreamEventType
    delta_text: str = ""
    generation: LLMGeneration | None = None


class LLMProvider(Protocol):
    @property
    def info(self) -> LLMProviderInfo:
        """Return provider configuration."""

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        """Generate one normalized text response."""

    def stream(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> Iterator[LLMStreamEvent]:
        """Yield normalized text deltas and one completion event."""
