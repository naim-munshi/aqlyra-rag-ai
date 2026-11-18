"""Durability gates for user documents and generated artifacts.

Document uploads still require an independently verified durable local mount
or their existing separately accepted cloud-upload workflow. Generated
artifacts may use the existing private Neon S3-compatible object store.
"""
from app.config.settings import Settings, settings


def local_writes_permitted(cfg: Settings = settings) -> bool:
    return cfg.APP_ENV != "production" or cfg.LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED


def private_object_storage_configured(cfg: Settings = settings) -> bool:
    """Configuration predicate only; does not prove provider write/read durability."""
    return bool(
        cfg.PRIVATE_OBJECT_STORAGE_ENABLED
        and cfg.AWS_ENDPOINT_URL_S3
        and cfg.AWS_ACCESS_KEY_ID
        and cfg.AWS_SECRET_ACCESS_KEY
        and cfg.AWS_REGION
        and cfg.OBJECT_STORAGE_BUCKET
    )


def artifact_writes_permitted(cfg: Settings = settings) -> bool:
    # Prefer the durable private object store in production. The explicit
    # ephemeral switch remains a disposable test fallback only when private
    # object storage is not configured. It never enables document uploads.
    return (
        private_object_storage_configured(cfg)
        or local_writes_permitted(cfg)
        or (
            cfg.APP_ENV == "production"
            and cfg.EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED
        )
    )
