from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


ChunkRole = Literal[
    "content",
    "summary",
    "proposition",
]


class RetrievalSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=4000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
    )

    document_ids: tuple[str, ...] = Field(
        default=(),
    )

    chunk_roles: tuple[ChunkRole, ...] = Field(
        default=(
            "content",
            "summary",
        ),
    )

    min_similarity: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
    )

    @field_validator("query")
    @classmethod
    def validate_query(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "query cannot be empty"
            )

        return cleaned

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) > 100:
            raise ValueError(
                "document_ids cannot contain "
                "more than 100 items"
            )

        cleaned = tuple(
            document_id.strip()
            for document_id in value
        )

        if any(
            not document_id
            for document_id in cleaned
        ):
            raise ValueError(
                "document_ids cannot contain "
                "empty values"
            )

        if len(set(cleaned)) != len(cleaned):
            raise ValueError(
                "document_ids cannot contain "
                "duplicates"
            )

        return cleaned

    @field_validator("chunk_roles")
    @classmethod
    def validate_chunk_roles(
        cls,
        value: tuple[ChunkRole, ...],
    ) -> tuple[ChunkRole, ...]:
        if not value:
            raise ValueError(
                "chunk_roles cannot be empty"
            )

        if len(set(value)) != len(value):
            raise ValueError(
                "chunk_roles cannot contain "
                "duplicates"
            )

        return value


class RetrievalCitationResponse(BaseModel):
    filename: str
    source_label: str
    section_path: list[str]
    start_page: int | None
    end_page: int | None


class RetrievalItemResponse(BaseModel):
    chunk_id: str
    document_id: str
    parent_chunk_id: str | None
    chunk_role: ChunkRole
    chunk_level: int = Field(ge=0)
    chunk_index: int = Field(ge=1)
    source_label: str
    section_path: list[str]
    content: str

    similarity_score: float = Field(
        ge=-1.0,
        le=1.0,
    )

    cosine_distance: float = Field(
        ge=0.0,
        le=2.0,
    )

    citation: RetrievalCitationResponse

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class RetrievalSearchResponse(BaseModel):
    query: str
    total: int = Field(ge=0)
    items: list[RetrievalItemResponse]
