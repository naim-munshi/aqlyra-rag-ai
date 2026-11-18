"""Durability gates for user documents and generated artifacts.

Document uploads still require an independently verified durable local mount
or their existing separately accepted cloud-upload workflow. Generated
artifacts may use the existing private Neon S3-compatible object store.
"""
from app.config.settings import Settings, settings


def local_writes_permitted(cfg: Settings = settings) -> bool:
    return cfg.APP_ENV != "production" or cfg.LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED


def private_object_storage_selected(cfg: Settings = settings) -> bool:
    return cfg.PRIVATE_OBJECT_STORAGE_ENABLED


def private_object_storage_configured(cfg: Settings = settings) -> bool:
    """Configuration predicate only; it does not prove provider durability."""
    return bool(
        private_object_storage_selected(cfg)
        and cfg.AWS_ENDPOINT_URL_S3
        and cfg.AWS_ACCESS_KEY_ID
        and cfg.AWS_SECRET_ACCESS_KEY
        and cfg.AWS_REGION
        and cfg.OBJECT_STORAGE_BUCKET
    )


def artifact_writes_permitted(cfg: Settings = settings) -> bool:
    # An explicitly selected but incomplete private backend fails closed.
    # It must never silently fall back to the disposable local filesystem.
    if private_object_storage_selected(cfg):
        return private_object_storage_configured(cfg)
    # Development can use local files. Production can opt into local writes
    # only after the mount is verified durable or disposable test mode is on.
    return local_writes_permitted(cfg) or (
        cfg.APP_ENV == "production" and cfg.EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED
    )
