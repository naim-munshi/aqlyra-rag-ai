from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM
    OPENAI_API_KEY: str = ""

    # Document uploads
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE_MB: int = 25
    UPLOAD_CHUNK_SIZE_BYTES: int = 1_048_576
    ALLOWED_DOCUMENT_EXTENSIONS: str = (
        ".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv"
    )

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_document_extensions(self) -> set[str]:
        return {
            extension.strip().lower()
            for extension in self.ALLOWED_DOCUMENT_EXTENSIONS.split(",")
            if extension.strip()
        }


settings = Settings()