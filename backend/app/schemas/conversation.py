from datetime import datetime
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


ConversationMode = Literal[
    "normal",
    "knowledge",
]


class ConversationCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    title: str = Field(
        default="New chat",
        min_length=1,
        max_length=255,
    )

    mode: ConversationMode = "normal"

    @field_validator("title")
    @classmethod
    def normalize_title(
        cls,
        value: str,
    ) -> str:
        cleaned = " ".join(
            value.split()
        )

        if not cleaned:
            raise ValueError(
                "Conversation title cannot be empty"
            )

        return cleaned


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    mode: ConversationMode | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = " ".join(
            value.split()
        )

        if not cleaned:
            raise ValueError(
                "Conversation title cannot be empty"
            )

        return cleaned

    @model_validator(mode="after")
    def require_change(
        self,
    ) -> Self:
        if (
            self.title is None
            and self.mode is None
        ):
            raise ValueError(
                "At least one field must be updated"
            )

        return self


class ConversationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: str
    title: str
    mode: ConversationMode
    created_at: datetime
    updated_at: datetime
