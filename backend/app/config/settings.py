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
    PROJECT_NAME: str = (
        "Aqlyra RAG AI"
    )
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: (
        int
    ) = 30

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = (
        "redis://localhost:6379/0"
    )

    # Provider credentials
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # Embeddings
    EMBEDDING_PROVIDER: str = (
        "deterministic"
    )
    EMBEDDING_MODEL: str = (
        "text-embedding-3-small"
    )
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_MAX_BATCH_SIZE: (
        int
    ) = 128
    EMBEDDING_TIMEOUT_SECONDS: (
        float
    ) = 30.0
    EMBEDDING_MAX_RETRIES: int = 3

    # LLM generation
    LLM_PROVIDER: str = (
        "deterministic"
    )
    LLM_MODEL: str = "gpt-5"
    LLM_MAX_OUTPUT_TOKENS: int = 800
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_RETRIES: int = 2

    # Document uploads
    UPLOAD_DIR: Path = Path(
        "uploads"
    )
    MAX_UPLOAD_SIZE_MB: int = 25
    UPLOAD_CHUNK_SIZE_BYTES: int = (
        1_048_576
    )
    ALLOWED_DOCUMENT_EXTENSIONS: (
        str
    ) = (
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
        normalized = (
            value.strip().lower()
        )

        if normalized not in {
            "deterministic",
            "openai",
        }:
            raise ValueError(
                "EMBEDDING_PROVIDER "
                "must be 'deterministic' "
                "or 'openai'"
            )

        return normalized

    @field_validator(
        "LLM_PROVIDER"
    )
    @classmethod
    def validate_llm_provider(
        cls,
        value: str,
    ) -> str:
        normalized = (
            value.strip().lower()
        )

        if normalized not in {
            "deterministic",
            "groq",
            "openai",
        }:
            raise ValueError(
                "LLM_PROVIDER must be "
                "'deterministic', "
                "'groq', or 'openai'"
            )

        return normalized

    @field_validator(
        "EMBEDDING_DIMENSION",
        "EMBEDDING_MAX_BATCH_SIZE",
        "LLM_MAX_OUTPUT_TOKENS",
    )
    @classmethod
    def validate_positive_integer(
        cls,
        value: int,
    ) -> int:
        if value < 1:
            raise ValueError(
                "Value must be positive"
            )

        return value

    @field_validator(
        "EMBEDDING_MAX_RETRIES",
        "LLM_MAX_RETRIES",
    )
    @classmethod
    def validate_nonnegative_integer(
        cls,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError(
                "Retry count cannot "
                "be negative"
            )

        return value

    @field_validator(
        "EMBEDDING_TIMEOUT_SECONDS",
        "LLM_TIMEOUT_SECONDS",
    )
    @classmethod
    def validate_positive_timeout(
        cls,
        value: float,
    ) -> float:
        if value <= 0:
            raise ValueError(
                "Timeout must be positive"
            )

        return value

    @model_validator(mode="after")
    def validate_provider_configuration(
        self,
    ) -> Self:
        if (
            self.EMBEDDING_DIMENSION
            != 384
        ):
            raise ValueError(
                "EMBEDDING_DIMENSION "
                "must be 384 because "
                "the database vector "
                "column uses VECTOR(384)"
            )

        if not self.EMBEDDING_MODEL.strip():
            raise ValueError(
                "EMBEDDING_MODEL "
                "cannot be empty"
            )

        if not self.LLM_MODEL.strip():
            raise ValueError(
                "LLM_MODEL cannot be empty"
            )

        uses_openai = (
            self.EMBEDDING_PROVIDER
            == "openai"
            or self.LLM_PROVIDER
            == "openai"
        )

        if (
            uses_openai
            and not
            self.OPENAI_API_KEY.strip()
        ):
            raise ValueError(
                "OPENAI_API_KEY is "
                "required when an "
                "OpenAI provider "
                "is enabled"
            )

        if (
            self.LLM_PROVIDER == "groq"
            and not
            self.GROQ_API_KEY.strip()
        ):
            raise ValueError(
                "GROQ_API_KEY is required "
                "when the Groq LLM "
                "provider is enabled"
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
            in (
                self
                .ALLOWED_DOCUMENT_EXTENSIONS
                .split(",")
            )
            if extension.strip()
        }


settings = Settings()