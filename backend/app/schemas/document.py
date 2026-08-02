from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DocumentStatus = Literal[
    "uploaded",
    "queued",
    "processing",
    "ready",
    "failed",
]


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    content_type: str
    file_extension: str
    file_size: int = Field(ge=0)
    checksum_sha256: str
    status: DocumentStatus
    language: str | None
    page_count: int | None
    word_count: int | None
    parsing_quality_score: float | None
    requires_ocr: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class DocumentUnitResponse(BaseModel):
    id: str
    document_id: str
    unit_index: int = Field(ge=1)
    unit_type: Literal[
        "page",
        "slide",
        "sheet",
        "section",
        "text",
    ]
    source_label: str
    content: str
    content_hash: str
    char_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    unit_metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUnitListResponse(BaseModel):
    document_id: str
    document_status: DocumentStatus
    items: list[DocumentUnitResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)