from dataclasses import dataclass
from typing import Protocol


class QueryRewriteError(Exception):
    """Base query rewriting failure."""


class QueryRewriteValidationError(
    QueryRewriteError
):
    """Raised when a rewritten query is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class QueryRewriterInfo:
    provider_name: str
    model_name: str


class QueryRewriter(Protocol):
    @property
    def info(self) -> QueryRewriterInfo:
        """Return query rewriter configuration."""

    def rewrite(
        self,
        query: str,
    ) -> str:
        """Return a retrieval-optimized query."""
