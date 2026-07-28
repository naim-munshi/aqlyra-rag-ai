from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str
    VERSION: str
    API_V1_STR: str
    DEBUG: bool

    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # OpenAI
    OPENAI_API_KEY: str

    # Uploads
    UPLOAD_DIR: str

    # Logging
    LOG_LEVEL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()