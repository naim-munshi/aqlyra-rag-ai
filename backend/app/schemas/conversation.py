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


class ConversationMessageCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    content: str = Field(
        min_length=1,
        max_length=4_000,
    )

    document_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    top_k: int = Field(
        default=8,
        ge=1,
        le=50,
    )

    @field_validator("content")
    @classmethod
    def normalize_content(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Message cannot be empty"
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


class MessageResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: str
    conversation_id: str

    role: Literal[
        "user",
        "assistant",
    ]

    mode: ConversationMode

    content: str

    provider_name: str | None
    model_name: str | None
    response_id: str | None

    citations: list[dict]

    is_refusal: bool

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    evidence_tokens: int | None

    created_at: datetime


class ChatTurnResponse(BaseModel):
    conversation_id: str
    mode: ConversationMode

    user_message: MessageResponse
    assistant_message: MessageResponse
