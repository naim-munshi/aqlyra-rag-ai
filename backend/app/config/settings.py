from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import UUID
from typing import Self

from pydantic import (
    Field,
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

    # Admin monitoring is disabled unless explicitly assigned to verified
    # immutable user UUIDs. Never use emails/usernames as admin identities.
    ADMIN_USER_IDS: str = ""

    # Verified identity
    EMAIL_VERIFICATION_REQUIRED: bool = True
    EMAIL_VERIFICATION_CODE_TTL_MINUTES: int = 10
    EMAIL_VERIFICATION_MAX_ATTEMPTS: int = 5
    EMAIL_VERIFICATION_RESEND_SECONDS: int = 60

    EMAIL_DELIVERY_PROVIDER: str = "smtp"
    RESEND_API_KEY: str = ""
    # Gmail HTTPS OAuth transport is optional until the mailbox owner grants
    # its gmail.send permission and securely configures the Render service.
    GMAIL_OAUTH_CLIENT_ID: str = ""
    GMAIL_OAUTH_CLIENT_SECRET: str = ""
    GMAIL_OAUTH_REFRESH_TOKEN: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Aqlyra"
    SMTP_USE_SSL: bool = True
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT_SECONDS: float = 10.0

    GOOGLE_CLIENT_ID: str = ""

    PASSWORD_RESET_CODE_TTL_MINUTES: int = 10
    PASSWORD_RESET_MAX_ATTEMPTS: int = 5
    PASSWORD_RESET_COOLDOWN_SECONDS: int = 60
    RATE_LIMIT_RESET_IP_LIMIT: int = 10
    RATE_LIMIT_RESET_IP_WINDOW_SECONDS: int = 3600

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=32)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=32)
    DATABASE_POOL_TIMEOUT_SECONDS: float = Field(default=30, gt=0, le=60)
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=60, le=7200)

    # Redis
    REDIS_URL: str = (
        "redis://localhost:6379/0"
    )

    # Rate limiting / abuse protection
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_CLIENT_IP_HEADER: str = (
        "X-Aqlyra-Client-IP"
    )
    # Public Render ingress must never trust caller-controlled IP headers.
    # Only explicitly listed, directly connected private proxy socket IPs
    # may supply this header in production. Leave empty on public Render.
    RATE_LIMIT_TRUSTED_PROXY_SOURCE_IPS: str = ""
    RATE_LIMIT_REDIS_TIMEOUT_SECONDS: float = 1.0

    RATE_LIMIT_REGISTER_IP_LIMIT: int = 5
    RATE_LIMIT_REGISTER_IP_WINDOW_SECONDS: int = 3_600

    RATE_LIMIT_LOGIN_IP_LIMIT: int = 10
    RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS: int = 60

    RATE_LIMIT_LOGIN_IDENTITY_LIMIT: int = 10
    RATE_LIMIT_LOGIN_IDENTITY_WINDOW_SECONDS: int = 300

    RATE_LIMIT_VERIFY_IP_LIMIT: int = 10
    RATE_LIMIT_VERIFY_IP_WINDOW_SECONDS: int = 300

    RATE_LIMIT_RESEND_IP_LIMIT: int = 5
    RATE_LIMIT_RESEND_IP_WINDOW_SECONDS: int = 3_600

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
        "qwen/qwen3.8-27b"
    )
    HF_TOKEN: str = ""

    # Opt-in live web research. Never use deterministic providers as real search.
    # Public browser automation MVP; deliberately off by default.
    BROWSER_AGENT_ENABLED: bool = False
    BROWSER_AGENT_ALLOWED_HOSTS: str = ""
    WEB_RESEARCH_ENABLED: bool = False
    TAVILY_API_KEY: str = ""
    TAVILY_KEYLESS_ENABLED: bool = False
    # Keyless SearXNG-first search. A private, trusted HTTPS endpoint is
    # configured by the operator; never accept it from user/chat input.
    WEB_SEARCH_PROVIDER: str = "auto"  # auto | searxng | tavily
    SEARXNG_BASE_URL: str = ""
    SEARXNG_SERVICE_TOKEN: str = ""  # Optional trusted gateway token
    SEARXNG_READ_PAGES_ENABLED: bool = False

    # Real-time voice must stay disabled until a LiveKit worker and
    # real STT/TTS providers have passed the owner-controlled E2E gate.
    VOICE_AGENT_READY: bool = False
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    VOICE_AGENT_NAME: str = "aqlyra-voice"
    VOICE_STT_MODEL: str = "whisper-large-v3"
    VOICE_TTS_MODEL: str = "cartesia/sonic-3"
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

    # Durable Knowledge indexing. Disabled by default for legacy/staging.
    # Store queue state in existing Document.status (no schema migration).
    KNOWLEDGE_AUTO_INDEX_ENABLED: bool = False
    KNOWLEDGE_LEXICAL_FALLBACK_ENABLED: bool = False
    KNOWLEDGE_INDEX_POLL_SECONDS: int = Field(default=8, ge=2, le=120)
    KNOWLEDGE_PDF_OCR_ENABLED: bool = False
    KNOWLEDGE_PDF_OCR_MAX_PAGES: int = Field(default=20, ge=1, le=50)
    KNOWLEDGE_PDF_OCR_PAGE_TIMEOUT_SECONDS: int = Field(default=15, ge=5, le=45)

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

    # Private Neon branch-scoped S3-compatible storage (opt-in; not routed
    # to browser uploads until durable finalization and deletion are tested).
    PRIVATE_OBJECT_STORAGE_ENABLED: bool = False
    # Keep browser direct-upload API off until staging security acceptance.
    CLOUD_UPLOAD_PUBLIC_ENABLED: bool = False
    # Small authenticated browser-proxy uploads; no S3 browser CORS needed.
    CLOUD_UPLOAD_PROXY_ENABLED: bool = False
    OBJECT_STORAGE_BUCKET: str = ""
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-2"

    # Do not persist new user files to ephemeral production disks.
    LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED: bool = False

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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_postgresql_driver(
        cls,
        value: str,
    ) -> str:
        # Neon and libpq return postgresql:// by default, while Aqlyra
        # intentionally installs psycopg v3 rather than psycopg2.
        # Change only the SQLAlchemy driver selector, never credentials.
        if isinstance(value, str) and value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

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
        "EMAIL_VERIFICATION_CODE_TTL_MINUTES",
        "EMAIL_VERIFICATION_MAX_ATTEMPTS",
        "EMAIL_VERIFICATION_RESEND_SECONDS",
        "SMTP_PORT",
        "PASSWORD_RESET_CODE_TTL_MINUTES",
        "PASSWORD_RESET_MAX_ATTEMPTS",
        "PASSWORD_RESET_COOLDOWN_SECONDS",
        "RATE_LIMIT_RESET_IP_LIMIT",
        "RATE_LIMIT_RESET_IP_WINDOW_SECONDS",
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
        "SMTP_TIMEOUT_SECONDS",
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
        # Only disposable local SMTP sinks may use plain SMTP.
        # Production always requires an encrypted SMTP transport.
        if (
            self.APP_ENV.strip().lower() == "production"
            and self.EMAIL_DELIVERY_PROVIDER == "smtp"
            and not (self.SMTP_USE_SSL or self.SMTP_STARTTLS)
        ):
            raise ValueError(
                "Production SMTP requires SSL or STARTTLS"
            )

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
            "RATE_LIMIT_VERIFY_IP_LIMIT": (
                self.RATE_LIMIT_VERIFY_IP_LIMIT
            ),
            "RATE_LIMIT_VERIFY_IP_WINDOW_SECONDS": (
                self.RATE_LIMIT_VERIFY_IP_WINDOW_SECONDS
            ),
            "RATE_LIMIT_RESEND_IP_LIMIT": (
                self.RATE_LIMIT_RESEND_IP_LIMIT
            ),
            "RATE_LIMIT_RESEND_IP_WINDOW_SECONDS": (
                self.RATE_LIMIT_RESEND_IP_WINDOW_SECONDS
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

        if (
            self.EMAIL_VERIFICATION_REQUIRED
            and not self.SMTP_HOST.strip()
        ):
            raise ValueError(
                "SMTP_HOST is required when email "
                "verification is enabled"
            )

        if not self.SMTP_FROM_NAME.strip():
            raise ValueError(
                "SMTP_FROM_NAME cannot be empty"
            )

        return self

    @model_validator(mode="after")
    def validate_cloud_upload_gate(self) -> Self:
        if (self.CLOUD_UPLOAD_PUBLIC_ENABLED or self.CLOUD_UPLOAD_PROXY_ENABLED) and not self.PRIVATE_OBJECT_STORAGE_ENABLED:
            raise ValueError("Cloud upload requires private object storage")
        return self

    @model_validator(mode="after")
    def validate_private_object_storage(self) -> Self:
        if not self.PRIVATE_OBJECT_STORAGE_ENABLED:
            return self
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.OBJECT_STORAGE_BUCKET):
            raise ValueError("OBJECT_STORAGE_BUCKET must be a DNS-safe private bucket")
        if not all((self.AWS_ACCESS_KEY_ID, self.AWS_SECRET_ACCESS_KEY)):
            raise ValueError("Neon private object storage credentials are required")
        if self.AWS_REGION not in {
            "us-east-1", "us-east-2", "eu-central-1", "ap-southeast-1"
        }:
            raise ValueError("Unsupported Neon private storage region")
        endpoint = urlsplit(self.AWS_ENDPOINT_URL_S3)
        if (
            endpoint.scheme != "https"
            or not (endpoint.hostname or "").endswith(".aws.neon.tech")
            or endpoint.username or endpoint.password
            or endpoint.path not in ("", "/") or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("AWS_ENDPOINT_URL_S3 must be a Neon HTTPS storage endpoint")
        try:
            if endpoint.port is not None:
                raise ValueError("Neon private storage does not use custom ports")
        except ValueError as exc:
            raise ValueError("Neon private storage does not use custom ports") from exc
        return self

    @field_validator("ADMIN_USER_IDS")
    @classmethod
    def validate_admin_ids(cls, value: str) -> str:
        ids = [entry.strip().lower() for entry in value.split(",") if entry.strip()]
        if len(ids) > 5 or len(ids) != len(set(ids)):
            raise ValueError("ADMIN_USER_IDS must contain up to 5 unique UUIDs")
        for entry in ids:
            try:
                parsed = UUID(entry)
            except (TypeError, ValueError) as exc:
                raise ValueError("ADMIN_USER_IDS accepts UUIDs only") from exc
            if str(parsed) != entry:
                raise ValueError("ADMIN_USER_IDS requires canonical UUIDs")
        return ",".join(ids)

    @field_validator("EMAIL_DELIVERY_PROVIDER")
    @classmethod
    def validate_email_delivery_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"smtp", "resend", "gmail_api"}:
            raise ValueError(
                "EMAIL_DELIVERY_PROVIDER must be smtp, resend, or gmail_api"
            )
        return normalized

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

        if self.EMBEDDING_PROVIDER == "deterministic":
            raise ValueError(
                "EMBEDDING_PROVIDER must not be "
                "deterministic in production"
            )

        if self.DEBUG:
            raise ValueError(
                "DEBUG must be false in production"
            )

        if not self.EMAIL_VERIFICATION_REQUIRED:
            raise ValueError(
                "EMAIL_VERIFICATION_REQUIRED must be "
                "true in production"
            )

        email_values = {
            "SMTP_FROM_EMAIL": self.SMTP_FROM_EMAIL,
            "GOOGLE_CLIENT_ID": self.GOOGLE_CLIENT_ID,
        }
        if self.EMAIL_DELIVERY_PROVIDER == "smtp":
            email_values.update({
                "SMTP_USERNAME": self.SMTP_USERNAME,
                "SMTP_PASSWORD": self.SMTP_PASSWORD,
            })
        elif self.EMAIL_DELIVERY_PROVIDER == "resend":
            email_values["RESEND_API_KEY"] = self.RESEND_API_KEY
        elif self.EMAIL_DELIVERY_PROVIDER == "gmail_api":
            email_values.update({
                "GMAIL_OAUTH_CLIENT_ID": self.GMAIL_OAUTH_CLIENT_ID,
                "GMAIL_OAUTH_CLIENT_SECRET": self.GMAIL_OAUTH_CLIENT_SECRET,
                "GMAIL_OAUTH_REFRESH_TOKEN": self.GMAIL_OAUTH_REFRESH_TOKEN,
            })
        for setting_name, setting_value in email_values.items():
            if not setting_value.strip():
                raise ValueError(
                    f"{setting_name} is required in production"
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