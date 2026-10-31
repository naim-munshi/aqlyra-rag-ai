"""Prevent new user files being stored on an unverified ephemeral production disk.

Existing documents and artifacts remain accessible. Core currently has no
accepted private remote artifact storage path; verify a durable local mount
and complete a restore rehearsal before enabling its local write path.
"""
from app.config.settings import Settings, settings


def local_writes_permitted(cfg: Settings = settings) -> bool:
    return cfg.APP_ENV != "production" or cfg.LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED


def artifact_writes_permitted(cfg: Settings = settings) -> bool:
    # Remote storage is explicit opt-in and never falls back to local disk.
    return cfg.ARTIFACT_REMOTE_STORAGE_ENABLED or local_writes_permitted(cfg)
