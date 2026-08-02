from dataclasses import dataclass
from typing import (
    Protocol,
    Sequence,
    runtime_checkable,
)


class EmbeddingError(Exception):
    """Base exception for embedding failures."""


class EmbeddingValidationError(
    EmbeddingError
):
    """Raised when embedding input or output is invalid."""


class EmbeddingProviderNotFoundError(
    EmbeddingError
):
    """Raised when an embedding provider is not registered."""


class EmbeddingProviderRequestError(
    EmbeddingError
):
    """Raised when an external embedding request fails."""


@dataclass(frozen=True, slots=True)
class EmbeddingProviderInfo:
    provider_name: str
    model_name: str
    dimension: int
    max_batch_size: int

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError(
                "provider_name cannot be empty"
            )

        if not self.model_name.strip():
            raise ValueError(
                "model_name cannot be empty"
            )

        if self.dimension <= 0:
            raise ValueError(
                "dimension must be positive"
            )

        if self.max_batch_size <= 0:
            raise ValueError(
                "max_batch_size must be positive"
            )


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def info(
        self,
    ) -> EmbeddingProviderInfo:
        """Return provider configuration."""

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """Embed multiple document texts."""

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Embed one search query."""
