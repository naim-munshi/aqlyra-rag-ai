from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.conversation import (
    ConversationMode,
)


class VoiceSessionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    mode: ConversationMode = "normal"

    conversation_id: str | None = None

    title: str = Field(
        default="Voice conversation",
        min_length=1,
        max_length=255,
    )

    document_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    @field_validator("conversation_id")
    @classmethod
    def normalize_conversation_id(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None

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
                "Voice conversation title "
                "cannot be empty"
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


class VoiceSessionResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str

    conversation_id: str
    mode: ConversationMode
