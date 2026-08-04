from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class RetrievalEvidence(Protocol):
    """Structural contract for a retrieved evidence chunk."""

    chunk_id: str
    document_id: str
    original_filename: str
    parent_chunk_id: str | None
    chunk_role: str
    chunk_level: int
    chunk_index: int
    source_label: str
    section_path: Sequence[str]
    content: str
    start_page: int | None
    end_page: int | None
    similarity_score: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EvidenceContextConfig:
    max_context_tokens: int = 2_400
    max_source_tokens: int = 700
    max_sources: int = 8
    min_similarity: float = -1.0
    include_roles: tuple[str, ...] = (
        "content",
        "summary",
        "proposition",
    )

    def __post_init__(self) -> None:
        if self.max_context_tokens < 1:
            raise ValueError(
                "max_context_tokens must be positive"
            )

        if self.max_source_tokens < 1:
            raise ValueError(
                "max_source_tokens must be positive"
            )

        if self.max_source_tokens > self.max_context_tokens:
            raise ValueError(
                "max_source_tokens cannot exceed "
                "max_context_tokens"
            )

        if self.max_sources < 1:
            raise ValueError(
                "max_sources must be positive"
            )

        if not -1.0 <= self.min_similarity <= 1.0:
            raise ValueError(
                "min_similarity must be between "
                "-1.0 and 1.0"
            )

        if not self.include_roles:
            raise ValueError(
                "include_roles cannot be empty"
            )


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    chunk_id: str
    document_id: str
    original_filename: str
    parent_chunk_id: str | None
    chunk_role: str
    chunk_level: int
    chunk_index: int
    source_label: str
    section_path: tuple[str, ...]
    start_page: int | None
    end_page: int | None
    similarity_score: float
    content: str
    was_truncated: bool


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    text: str
    sources: tuple[EvidenceSource, ...]
    estimated_tokens: int
    skipped_count: int
    was_truncated: bool

    @property
    def has_evidence(self) -> bool:
        return bool(self.sources)
