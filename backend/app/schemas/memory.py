from datetime import datetime
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


MemoryKind = Literal[
    "fact",
    "preference",
    "goal",
    "decision",
]


def _clean_content(value: str) -> str:
    cleaned = " ".join(value.split())

    if not cleaned:
        raise ValueError(
            "Memory content cannot be empty"
        )

    return cleaned


class MemoryCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    kind: MemoryKind

    content: str = Field(
        min_length=1,
        max_length=2_000,
    )

    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    @field_validator("content")
    @classmethod
    def normalize_content(
        cls,
        value: str,
    ) -> str:
        return _clean_content(value)


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    kind: MemoryKind | None = None

    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=2_000,
    )

    importance: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    is_active: bool | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return _clean_content(value)

    @model_validator(mode="after")
    def require_change(
        self,
    ) -> Self:
        if all(
            value is None
            for value in (
                self.kind,
                self.content,
                self.importance,
                self.confidence,
                self.is_active,
            )
        ):
            raise ValueError(
                "At least one field must be updated"
            )

        return self


class MemoryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: str
    kind: MemoryKind
    content: str
    importance: float
    confidence: float
    source_message_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
