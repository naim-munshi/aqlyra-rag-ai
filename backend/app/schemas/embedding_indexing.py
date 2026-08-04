from pydantic import BaseModel, Field


class EmbeddingReindexResponse(BaseModel):
    document_id: str
    provider_name: str
    model_name: str

    dimension: int = Field(
        ge=1,
    )

    chunk_count: int = Field(
        ge=0,
    )

    replaced_count: int = Field(
        ge=0,
    )

    created_count: int = Field(
        ge=0,
    )
