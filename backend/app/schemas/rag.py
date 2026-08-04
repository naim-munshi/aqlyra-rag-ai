from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


ChunkRole = Literal[
    "content",
    "summary",
    "proposition",
]


class RAGAnswerRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    question: str = Field(
        min_length=1,
        max_length=4_000,
    )

    top_k: int = Field(
        default=8,
        ge=1,
        le=50,
    )

    document_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    chunk_roles: list[ChunkRole] = Field(
        default_factory=lambda: [
            "content",
            "summary",
        ]
    )

    min_similarity: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
    )

    max_context_tokens: int = Field(
        default=2_400,
        ge=128,
        le=20_000,
    )

    max_source_tokens: int = Field(
        default=700,
        ge=32,
        le=5_000,
    )

    max_sources: int = Field(
        default=8,
        ge=1,
        le=20,
    )

    @field_validator("question")
    @classmethod
    def normalize_question(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Question cannot be empty"
            )

        return cleaned

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(
        cls,
        values: list[str],
    ) -> list[str]:
        cleaned = [
            value.strip()
            for value in values
        ]

        if any(
            not value
            for value in cleaned
        ):
            raise ValueError(
                "Document IDs cannot be empty"
            )

        if len(cleaned) != len(
            set(cleaned)
        ):
            raise ValueError(
                "Document IDs must be unique"
            )

        return cleaned

    @field_validator("chunk_roles")
    @classmethod
    def validate_chunk_roles(
        cls,
        values: list[ChunkRole],
    ) -> list[ChunkRole]:
        if not values:
            raise ValueError(
                "At least one chunk role "
                "is required"
            )

        if len(values) != len(
            set(values)
        ):
            raise ValueError(
                "Chunk roles must be unique"
            )

        return values

    @model_validator(mode="after")
    def validate_context_budget(
        self,
    ) -> Self:
        if (
            self.max_source_tokens
            > self.max_context_tokens
        ):
            raise ValueError(
                "max_source_tokens cannot exceed "
                "max_context_tokens"
            )

        return self


class RAGCitationResponse(BaseModel):
    source_id: str

    chunk_id: str
    document_id: str
    parent_chunk_id: str | None

    filename: str

    chunk_role: ChunkRole
    chunk_level: int
    chunk_index: int

    source_label: str
    section_path: list[str]

    start_page: int | None
    end_page: int | None

    similarity_score: float

    excerpt: str
    was_truncated: bool


class RAGUsageResponse(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    evidence_tokens: int


class RAGAnswerResponse(BaseModel):
    question: str
    answer: str

    is_refusal: bool

    provider_name: str
    model_name: str
    response_id: str | None

    citations: list[RAGCitationResponse]
    citation_count: int

    retrieved_count: int
    context_source_count: int
    skipped_evidence_count: int
    evidence_was_truncated: bool

    usage: RAGUsageResponse
