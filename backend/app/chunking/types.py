from dataclasses import dataclass, field
from typing import Any, Literal


ChunkRole = Literal[
    "content",
    "summary",
    "proposition",
]


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    strategy_version: str = "iahc-x-v1"
    default_target_tokens: int = 320
    min_chunk_tokens: int = 80
    max_chunk_tokens: int = 520
    overlap_tokens: int = 48
    parent_summary_tokens: int = 120

    def __post_init__(self) -> None:
        if self.default_target_tokens <= 0:
            raise ValueError(
                "default_target_tokens must be positive"
            )

        if self.min_chunk_tokens <= 0:
            raise ValueError(
                "min_chunk_tokens must be positive"
            )

        if self.max_chunk_tokens < (
            self.default_target_tokens
        ):
            raise ValueError(
                "max_chunk_tokens cannot be smaller "
                "than default_target_tokens"
            )

        if self.overlap_tokens < 0:
            raise ValueError(
                "overlap_tokens cannot be negative"
            )

        if self.overlap_tokens >= (
            self.default_target_tokens
        ):
            raise ValueError(
                "overlap_tokens must be smaller "
                "than default_target_tokens"
            )

        if self.parent_summary_tokens <= 0:
            raise ValueError(
                "parent_summary_tokens must be positive"
            )


@dataclass(frozen=True, slots=True)
class ChunkSource:
    document_id: str
    document_label: str
    unit_id: str
    unit_index: int
    unit_type: str
    source_label: str
    content: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    id: str
    document_id: str
    document_unit_id: str
    parent_chunk_id: str | None
    chunk_index: int
    chunk_level: int
    chunk_role: ChunkRole
    source_label: str
    section_path: tuple[str, ...]
    content: str
    embedding_content: str
    content_hash: str
    token_count: int
    char_count: int
    word_count: int
    start_char: int | None
    end_char: int | None
    start_page: int | None
    end_page: int | None
    strategy_version: str
    metadata: dict[str, Any]
