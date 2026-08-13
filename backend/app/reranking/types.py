from dataclasses import dataclass
from typing import Protocol

from app.retrieval import RetrievalHit


class RerankerError(Exception):
    """Base exception for reranking failures."""


class RerankerValidationError(RerankerError):
    """Raised when reranker input or output is invalid."""


@dataclass(frozen=True, slots=True)
class RerankerInfo:
    provider_name: str
    model_name: str


@dataclass(frozen=True, slots=True)
class RerankerScore:
    chunk_id: str
    score: float


class RerankerProvider(Protocol):
    @property
    def info(self) -> RerankerInfo:
        """Return reranker provider configuration."""

    def rerank(
        self,
        *,
        query: str,
        hits: tuple[RetrievalHit, ...],
    ) -> tuple[RerankerScore, ...]:
        """Score every supplied candidate."""
