from dataclasses import dataclass, field
from typing import Any


_ALLOWED_CHUNK_ROLES = frozenset(
    {
        "content",
        "summary",
        "proposition",
    }
)


class RetrievalError(Exception):
    """Base exception for retrieval failures."""


class RetrievalValidationError(RetrievalError):
    """Raised when a retrieval request is invalid."""


class RetrievalProviderError(RetrievalError):
    """Raised when the embedding provider is incompatible."""


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    user_id: str
    text: str
    top_k: int = 5
    document_ids: tuple[str, ...] = ()
    chunk_roles: tuple[str, ...] = (
        "content",
        "summary",
    )
    min_similarity: float | None = None

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise RetrievalValidationError(
                "user_id cannot be empty"
            )

        if not self.text.strip():
            raise RetrievalValidationError(
                "query text cannot be empty"
            )

        if not 1 <= self.top_k <= 50:
            raise RetrievalValidationError(
                "top_k must be between 1 and 50"
            )

        invalid_roles = (
            set(self.chunk_roles)
            - _ALLOWED_CHUNK_ROLES
        )

        if invalid_roles:
            raise RetrievalValidationError(
                "Unsupported chunk roles: "
                + ", ".join(
                    sorted(invalid_roles)
                )
            )

        if (
            self.min_similarity is not None
            and not -1.0
            <= self.min_similarity
            <= 1.0
        ):
            raise RetrievalValidationError(
                "min_similarity must be "
                "between -1.0 and 1.0"
            )

        if len(set(self.document_ids)) != len(
            self.document_ids
        ):
            raise RetrievalValidationError(
                "document_ids cannot contain duplicates"
            )


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    original_filename: str
    parent_chunk_id: str | None
    chunk_role: str
    chunk_level: int
    chunk_index: int
    source_label: str
    section_path: tuple[str, ...]
    content: str
    start_page: int | None
    end_page: int | None
    similarity_score: float
    cosine_distance: float
    ranking_score: float | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
