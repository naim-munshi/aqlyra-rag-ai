from dataclasses import dataclass

from app.rag.types import EvidenceSource


INSUFFICIENT_EVIDENCE_SENTINEL = (
    "INSUFFICIENT_EVIDENCE"
)


class GroundedAnswerError(Exception):
    """Base exception for grounded-answer failures."""


class GroundedPromptValidationError(
    GroundedAnswerError
):
    """Raised when question or prompt input is invalid."""


class MissingEvidenceError(
    GroundedAnswerError
):
    """Raised when no usable evidence is available."""


class GroundedAnswerGenerationError(
    GroundedAnswerError
):
    """Raised when generation returns unusable output."""


@dataclass(frozen=True, slots=True)
class GroundedPrompt:
    instructions: str
    input_text: str


@dataclass(frozen=True, slots=True)
class GroundedAnswerDraft:
    question: str
    answer_text: str
    sources: tuple[EvidenceSource, ...]

    provider_name: str
    model_name: str

    response_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    evidence_tokens: int
    skipped_evidence_count: int
    evidence_was_truncated: bool

    @property
    def indicates_insufficient_evidence(
        self,
    ) -> bool:
        return (
            self.answer_text.strip()
            == INSUFFICIENT_EVIDENCE_SENTINEL
        )

    @property
    def source_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            source.source_id
            for source in self.sources
        )
