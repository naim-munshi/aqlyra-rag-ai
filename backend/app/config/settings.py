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


from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    # Project
    APP_ENV: str = "development"
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

    # Rate limiting / abuse protection
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_CLIENT_IP_HEADER: str = (
        "X-Aqlyra-Client-IP"
    )
    RATE_LIMIT_REDIS_TIMEOUT_SECONDS: float = 1.0

    RATE_LIMIT_REGISTER_IP_LIMIT: int = 5
    RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS: int = 3_600

    RATE_LIMIT_LOGIN_IP_LIMIT: int = 10
    RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS: int = 60

    RATE_LIMIT_LOGIN_IDENTITY_LIMIT: int = 10
    RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS: int = 300

    RATE_LIMIT_UPLOAD_USER_LIMIT: int = 20
    RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS: int = 3_600

    RATE_LIMIT_PROCESS_USER_LIMIT: int = 30
    RATE_LIMIT_PROCESS_USER_WINDOW_SECONDS: int = 3_600

    RATE_LIMIT_RAG_USER_LIMIT: int = 20
    RATE_LIMIT_RAG_USER_WINDOW_SECONDS: int = 60

    RATE_LIMIT_CHAT_USER_LIMIT: int = 30
    RATE_LIMIT_CHAT_USER_WINDOW_SECONDS: int = 60

    RATE_LIMIT_VOICE_USER_LIMIT: int = 5
    RATE_LIMIT_VOICE_USER_WINDOW_SECONDS: int = 60

    # Operational alerting
    ALERTING_ENABLED: bool = False
    ALERT_BACKEND_BASE_URL: str = (
        "http://backend:8000/api/v1"
    )
    ALERT_POLL_INTERVAL_SECONDS: float = 30.0
    ALERT_STARTUP_GRACE_SECONDS: float = 60.0
    ALERT_READINESS_FAILURES: int = 3
    ALERT_RECOVERY_SUCCESSES: int = 2

    ALERT_HTTP_TIMEOUT_SECONDS: float = 5.0
    ALERT_WEBHOOK_URL: str = ""
    ALERT_WEBHOOK_BEARER_TOKEN: str = ""
    ALERT_WEBHOOK_TIMEOUT_SECONDS: float = 5.0

    ALERT_HTTP_5XX_RATIO_THRESHOLD: float = 0.10
    ALERT_HTTP_5XX_MIN_REQUESTS: int = 20
    ALERT_P95_LATENCY_SECONDS: float = 3.0
    ALERT_LATENCY_MIN_REQUESTS: int = 20

    ALERT_RATE_LIMIT_EXCEEDED_THRESHOLD: int = 50
    ALERT_RATE_LIMIT_BACKEND_UNAVAILABLE_THRESHOLD: int = 1
    ALERT_UNHANDLED_EXCEPTION_THRESHOLD: int = 1

    ALERT_HEARTBEAT_FILE: str = (
        "/tmp/aqlyra-alerting-heartbeat"
    )
    ALERT_HEARTBEAT_MAX_AGE_SECONDS: float = 180.0

    # Provider credentials
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    CONVERSE_VISION_MODEL: str = (
        "qwen/qwen3.6-27b"
    )
    HF_TOKEN: str = ""

    # Realtime voice
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    VOICE_AGENT_NAME: str = "aqlyra-voice"
    VOICE_STT_MODEL: str = "whisper-large-v3"
    VOICE_TTS_MODEL: str = "cartesia/sonic-3.5"
    VOICE_TTS_VOICE: str = (
        "a5136bf9-224c-4d76-b823-52bd5efcffcc"
    )
    VOICE_TTS_DEFAULT_LANGUAGE: str = "en"

    # Embeddings
    EMBEDDING_PROVIDER: str = (
        "deterministic"
    )
    EMBEDDING_MODEL: str = (
        "deterministic-sha256-v1"
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
    LLM_REASONING_EFFORT: str = ""

    # RAG reranking
    RAG_GROUNDING_VERIFIER_ENABLED: bool = False
    RAG_RERANKER_ENABLED: bool = False
    RERANKER_PROVIDER: str = "llm"
    RERANKER_CANDIDATE_DEPTH: int = 15
    RERANKER_MAX_CANDIDATE_CHARS: int = 900
    RERANKER_MAX_OUTPUT_TOKENS: int = 1_024
    RERANKER_REASONING_EFFORT: str = "low"

    # RAG query rewriting
    RAG_QUERY_REWRITE_ENABLED: bool = False
    QUERY_REWRITER_PROVIDER: str = "llm"
    QUERY_REWRITER_MAX_CHARS: int = 500
    QUERY_REWRITER_MAX_OUTPUT_TOKENS: int = 256
    QUERY_REWRITER_REASONING_EFFORT: str = "low"

    # Personal memory extraction
    MEMORY_AUTO_EXTRACT_ENABLED: bool = False
    MEMORY_EXTRACTION_MAX_CANDIDATES: int = 4

    # Personal memory chat context
    MEMORY_CHAT_ENABLED: bool = False
    MEMORY_CHAT_TOP_K: int = 5
    MEMORY_CHAT_MIN_SIMILARITY: float = 0.35

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
        ".txt,.md,.csv,.png,.jpg,.jpeg,.webp"
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
            "huggingface",
            "openai",
        }:
            raise ValueError(
                "EMBEDDING_PROVIDER must be "
                "'deterministic', "
                "'huggingface', or 'openai'"
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
        "RERANKER_PROVIDER"
    )
    @classmethod
    def validate_reranker_provider(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if normalized not in {
            "identity",
            "llm",
        }:
            raise ValueError(
                "RERANKER_PROVIDER must be "
                "'identity' or 'llm'"
            )

        return normalized

    @field_validator(
        "QUERY_REWRITER_PROVIDER"
    )
    @classmethod
    def validate_query_rewriter_provider(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if normalized not in {
            "identity",
            "llm",
        }:
            raise ValueError(
                "QUERY_REWRITER_PROVIDER must be "
                "'identity' or 'llm'"
            )

        return normalized

    @field_validator(
        "QUERY_REWRITER_REASONING_EFFORT"
    )
    @classmethod
    def validate_query_rewriter_reasoning_effort(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if normalized not in {
            "low",
            "medium",
            "high",
        }:
            raise ValueError(
                "QUERY_REWRITER_REASONING_EFFORT "
                "must be 'low', 'medium', or 'high'"
            )

        return normalized

    @field_validator(
        "RERANKER_REASONING_EFFORT"
    )
    @classmethod
    def validate_reranker_reasoning_effort(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if normalized not in {
            "low",
            "medium",
            "high",
        }:
            raise ValueError(
                "RERANKER_REASONING_EFFORT must "
                "be 'low', 'medium', or 'high'"
            )

        return normalized

    @field_validator(
        "EMBEDDING_DIMENSION",
        "EMBEDDING_MAX_BATCH_SIZE",
        "LLM_MAX_OUTPUT_TOKENS",
        "RERANKER_CANDIDATE_DEPTH",
        "RERANKER_MAX_CANDIDATE_CHARS",
        "RERANKER_MAX_OUTPUT_TOKENS",
        "QUERY_REWRITER_MAX_CHARS",
        "QUERY_REWRITER_MAX_OUTPUT_TOKENS",
        "MEMORY_EXTRACTION_MAX_CANDIDATES",
        "MEMORY_CHAT_TOP_K",
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

        if self.RERANKER_CANDIDATE_DEPTH > 50:
            raise ValueError(
                "RERANKER_CANDIDATE_DEPTH "
                "cannot exceed 50"
            )

        if (
            self.RAG_RERANKER_ENABLED
            and self.RERANKER_PROVIDER == "llm"
            and self.LLM_PROVIDER == "deterministic"
        ):
            raise ValueError(
                "LLM reranking requires a "
                "non-deterministic LLM provider"
            )

        if (
            self.RAG_QUERY_REWRITE_ENABLED
            and self.QUERY_REWRITER_PROVIDER == "llm"
            and self.LLM_PROVIDER == "deterministic"
        ):
            raise ValueError(
                "LLM query rewriting requires a "
                "non-deterministic LLM provider"
            )

        if (
            self.MEMORY_EXTRACTION_MAX_CANDIDATES
            > 8
        ):
            raise ValueError(
                "MEMORY_EXTRACTION_MAX_CANDIDATES "
                "cannot exceed 8"
            )

        if (
            self.MEMORY_AUTO_EXTRACT_ENABLED
            and self.LLM_PROVIDER
            == "deterministic"
        ):
            raise ValueError(
                "Automatic memory extraction "
                "requires a non-deterministic "
                "LLM provider"
            )

        if self.MEMORY_CHAT_TOP_K > 20:
            raise ValueError(
                "MEMORY_CHAT_TOP_K cannot exceed 20"
            )

        if not (
            -1.0
            <= self.MEMORY_CHAT_MIN_SIMILARITY
            <= 1.0
        ):
            raise ValueError(
                "MEMORY_CHAT_MIN_SIMILARITY must be "
                "between -1.0 and 1.0"
            )

        if (
            self.MEMORY_CHAT_ENABLED
            and self.EMBEDDING_PROVIDER
            == "deterministic"
        ):
            raise ValueError(
                "Personal memory chat requires a "
                "semantic embedding provider"
            )

        if (
            self.EMBEDDING_PROVIDER
            == "huggingface"
            and not self.HF_TOKEN.strip()
        ):
            raise ValueError(
                "HF_TOKEN is required when the "
                "Hugging Face embedding provider "
                "is enabled"
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

        rate_limit_positive_values = {
            "RATE_LIMIT_REDIS_TIMEOUT_SECONDS": (
                self.RATE_LIMIT_REDIS_TIMEOUT_SECONDS
            ),
            "RATE_LIMIT_REGISTER_IP_LIMIT": (
                self.RATE_LIMIT_REGISTER_IP_LIMIT
            ),
            "RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS": (
                self.RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS
            ),
            "RATE_LIMIT_LOGIN_IP_LIMIT": (
                self.RATE_LIMIT_LOGIN_IP_LIMIT
            ),
            "RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS": (
                self.RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS
            ),
            "RATE_LIMIT_LOGIN_IDENTITY_LIMIT": (
                self.RATE_LIMIT_LOGIN_IDENTITY_LIMIT
            ),
            "RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS": (
                self.RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS
            ),
            "RATE_LIMIT_UPLOAD_USER_LIMIT": (
                self.RATE_LIMIT_UPLOAD_USER_LIMIT
            ),
            "RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS": (
                self.RATE_LIMIT_UPLOAD_USER_WINDOW_SECONDS
            ),
            "RATE_LIMIT_PROCESS_USER_LIMIT": (
                self.RATE_LIMIT_PROCESS_USER_LIMIT
            ),
            "RATE_LIMIT_PROCESS_USER_WINDOW_SECONDS": (
                self.RATE_LIMIT_PROCESS_USER_WINDOW_SECONDS
            ),
            "RATE_LIMIT_RAG_USER_LIMIT": (
                self.RATE_LIMIT_RAG_USER_LIMIT
            ),
            "RATE_LIMIT_RAG_USER_WINDOW_SECONDS": (
                self.RATE_LIMIT_RAG_USER_WINDOW_SECONDS
            ),
            "RATE_LIMIT_CHAT_USER_LIMIT": (
                self.RATE_LIMIT_CHAT_USER_LIMIT
            ),
            "RATE_LIMIT_CHAT_USER_WINDOW_SECONDS": (
                self.RATE_LIMIT_CHAT_USER_WINDOW_SECONDS
            ),
            "RATE_LIMIT_VOICE_USER_LIMIT": (
                self.RATE_LIMIT_VOICE_USER_LIMIT
            ),
            "RATE_LIMIT_VOICE_USER_WINDOW_SECONDS": (
                self.RATE_LIMIT_VOICE_USER_WINDOW_SECONDS
            ),
        }

        for (
            setting_name,
            setting_value,
        ) in rate_limit_positive_values.items():
            if setting_value <= 0:
                raise ValueError(
                    f"{setting_name} must be positive"
                )

        if not self.RATE_LIMIT_CLIENT_IP_HEADER.strip():
            raise ValueError(
                "RATE_LIMIT_CLIENT_IP_HEADER "
                "cannot be empty"
            )

        return self

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if normalized not in {
            "development",
            "test",
            "production",
        }:
            raise ValueError(
                "APP_ENV must be development, "
                "test, or production"
            )

        return normalized

    @model_validator(mode="after")
    def validate_production_security(
        self,
    ) -> Self:
        if self.APP_ENV != "production":
            return self

        if not self.RATE_LIMIT_ENABLED:
            raise ValueError(
                "RATE_LIMIT_ENABLED must be "
                "true in production"
            )

        if not self.REDIS_URL.strip():
            raise ValueError(
                "REDIS_URL must be configured "
                "in production"
            )

        if not self.RAG_GROUNDING_VERIFIER_ENABLED:
            raise ValueError(
                "RAG_GROUNDING_VERIFIER_ENABLED "
                "must be true in production"
            )

        if self.LLM_PROVIDER == "deterministic":
            raise ValueError(
                "LLM_PROVIDER must not be "
                "deterministic in production"
            )

        if self.DEBUG:
            raise ValueError(
                "DEBUG must be false in production"
            )

        origins = {
            origin.strip()
            for origin
            in self.CORS_ORIGINS.split(",")
            if origin.strip()
        }

        if not origins:
            raise ValueError(
                "CORS_ORIGINS must be configured "
                "in production"
            )

        unsafe_origins = (
            "*",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
        )

        for origin in origins:
            lowered = origin.casefold()

            if any(
                unsafe in lowered
                for unsafe in unsafe_origins
            ):
                raise ValueError(
                    "Production CORS_ORIGINS "
                    "cannot contain wildcard or "
                    "localhost origins"
                )

        secret = self.SECRET_KEY.strip()
        lowered_secret = secret.casefold()

        if (
            len(secret) < 32
            or "replace-with" in lowered_secret
            or "changeme" in lowered_secret
            or "placeholder" in lowered_secret
        ):
            raise ValueError(
                "Production SECRET_KEY must be "
                "a strong secret of at least "
                "32 characters"
            )

        try:
            database_url = make_url(
                self.DATABASE_URL
            )
        except Exception as exc:
            raise ValueError(
                "Production DATABASE_URL is invalid"
            ) from exc

        database_password = (
            database_url.password or ""
        ).strip()

        weak_database_passwords = {
            "postgres",
            "password",
            "changeme",
            "change-me",
            "replace-me",
            "placeholder",
        }

        if (
            not database_password
            or len(database_password) < 16
            or database_password.casefold()
            in weak_database_passwords
        ):
            raise ValueError(
                "Production DATABASE_URL must use "
                "a non-default database password "
                "of at least 16 characters"
            )

        return self

    @property
    def is_production(
        self,
    ) -> bool:
        return self.APP_ENV == "production"

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