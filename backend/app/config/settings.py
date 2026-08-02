from pathlib import Path
from typing import Self

from pydantic import (
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Ihsan RAG AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = (
        "redis://localhost:6379/0"
    )

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Embeddings
    EMBEDDING_PROVIDER: str = (
        "deterministic"
    )

    EMBEDDING_MODEL: str = (
        "text-embedding-3-small"
    )

    EMBEDDING_DIMENSION: int = 384

    EMBEDDING_MAX_BATCH_SIZE: int = 128

    EMBEDDING_TIMEOUT_SECONDS: float = 30.0

    EMBEDDING_MAX_RETRIES: int = 3

    # Document uploads
    UPLOAD_DIR: Path = Path("uploads")

    MAX_UPLOAD_SIZE_MB: int = 25

    UPLOAD_CHUNK_SIZE_BYTES: int = (
        1_048_576
    )

    ALLOWED_DOCUMENT_EXTENSIONS: str = (
        ".pdf,.docx,.xlsx,.pptx,"
        ".txt,.md,.csv"
    )

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator(
        "EMBEDDING_PROVIDER"
    )
    @classmethod
    def validate_embedding_provider(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        allowed_providers = {
            "deterministic",
            "openai",
        }

        if normalized not in allowed_providers:
            raise ValueError(
                "EMBEDDING_PROVIDER must be "
                "'deterministic' or 'openai'"
            )

        return normalized

    @field_validator(
        "EMBEDDING_DIMENSION",
        "EMBEDDING_MAX_BATCH_SIZE",
    )
    @classmethod
    def validate_positive_integer(
        cls,
        value: int,
    ) -> int:
        if value <= 0:
            raise ValueError(
                "Embedding numeric settings "
                "must be positive"
            )

        return value

    @field_validator(
        "EMBEDDING_MAX_RETRIES"
    )
    @classmethod
    def validate_retry_count(
        cls,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError(
                "EMBEDDING_MAX_RETRIES "
                "cannot be negative"
            )

        return value

    @field_validator(
        "EMBEDDING_TIMEOUT_SECONDS"
    )
    @classmethod
    def validate_embedding_timeout(
        cls,
        value: float,
    ) -> float:
        if value <= 0:
            raise ValueError(
                "EMBEDDING_TIMEOUT_SECONDS "
                "must be positive"
            )

        return value

    @model_validator(mode="after")
    def validate_embedding_configuration(
        self,
    ) -> Self:
        if self.EMBEDDING_DIMENSION != 384:
            raise ValueError(
                "EMBEDDING_DIMENSION must remain "
                "384 until the pgvector schema "
                "is migrated"
            )

        if not self.EMBEDDING_MODEL.strip():
            raise ValueError(
                "EMBEDDING_MODEL cannot be empty"
            )

        if (
            self.EMBEDDING_PROVIDER == "openai"
            and not self.OPENAI_API_KEY.strip()
        ):
            raise ValueError(
                "OPENAI_API_KEY is required when "
                "EMBEDDING_PROVIDER=openai"
            )

        return self

    @property
    def max_upload_size_bytes(
        self,
    ) -> int:
        return (
            self.MAX_UPLOAD_SIZE_MB
            * 1024
            * 1024
        )

    @property
    def allowed_document_extensions(
        self,
    ) -> set[str]:
        return {
            extension.strip().lower()
            for extension
            in self.ALLOWED_DOCUMENT_EXTENSIONS.split(
                ","
            )
            if extension.strip()
        }


settings = Settings()
