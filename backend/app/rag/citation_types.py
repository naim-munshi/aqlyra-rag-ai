from dataclasses import dataclass

from app.rag.answer_types import (
    GroundedAnswerDraft,
)
from app.rag.types import EvidenceSource


class CitationValidationError(Exception):
    """Base exception for citation validation failures."""


class MissingCitationError(
    CitationValidationError
):
    """Raised when an answer contains no citations."""


class UnknownCitationError(
    CitationValidationError
):
    """Raised when an answer references unknown sources."""


class MalformedCitationError(
    CitationValidationError
):
    """Raised when citation syntax is malformed."""


class UncitedClaimError(
    CitationValidationError
):
    """Raised when an answer block lacks source support."""


@dataclass(frozen=True, slots=True)
class ValidatedGroundedAnswer:
    draft: GroundedAnswerDraft
    citation_ids: tuple[str, ...]
    cited_sources: tuple[EvidenceSource, ...]
    citation_count: int
    is_refusal: bool

    @property
    def answer_text(self) -> str:
        return self.draft.answer_text

    @property
    def question(self) -> str:
        return self.draft.question

    @property
    def provider_name(self) -> str:
        return self.draft.provider_name

    @property
    def model_name(self) -> str:
        return self.draft.model_name
