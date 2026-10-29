"""Production persistence gate; never silently write user files to ephemeral disk.

Existing local files remain readable and deletable. New writes are accepted
only when a durable local mount was independently verified or (for generated
artifacts) the explicitly configured private remote object store is enabled.
"""
from app.config.settings import Settings, settings


def local_writes_permitted(cfg: Settings = settings) -> bool:
    return cfg.APP_ENV != "production" or cfg.LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED


def artifact_writes_permitted(cfg: Settings = settings) -> bool:
    return cfg.ARTIFACT_REMOTE_STORAGE_ENABLED or local_writes_permitted(cfg)
