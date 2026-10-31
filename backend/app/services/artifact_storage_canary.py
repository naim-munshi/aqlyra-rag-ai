"""Opt-in storage smoke using synthetic owner namespaces and no user records.

This verifies rendering and private object lifecycle, not login, AI quality,
backup recovery, or persistence across a real process restart.
"""
import logging
from uuid import uuid4

from app.config.settings import settings
from app.services import artifact_remote_storage as remote

logger = logging.getLogger(__name__)
FORMATS = ("md", "pdf", "docx", "xlsx", "pptx")


def run_artifact_storage_canary() -> bool:
    if not settings.ARTIFACT_STORAGE_CANARY_ON_STARTUP:
        return False
    if not settings.ARTIFACT_REMOTE_STORAGE_ENABLED:
        logger.warning("artifact_storage_canary status=SKIPPED reason=disabled")
        return False
    owner, other = str(uuid4()), str(uuid4())
    created: list[str] = []
    ok = False
    cleanup_ok = True
    try:
        for fmt in FORMATS:
            item = remote.create_artifact(
                user_id=owner, title="Synthetic storage acceptance", kind=fmt,
                content="# Storage acceptance\nSynthetic content only.",
                provider_name="operator-storage-probe", source_document_ids=[],
                citation_count=0,
            )
            artifact_id = item["id"]
            created.append(artifact_id)
            downloaded = remote.artifact_download(user_id=owner, artifact_id=artifact_id)
            if downloaded is None or not downloaded[0]:
                raise RuntimeError("Empty download")
            if len(downloaded[0]) != item["size"]:
                raise RuntimeError("Size mismatch")
            if remote.read_artifact(user_id=other, artifact_id=artifact_id) is not None:
                raise RuntimeError("Owner boundary failure")
            if remote.artifact_download(user_id=other, artifact_id=artifact_id) is not None:
                raise RuntimeError("Download owner boundary failure")
            if remote.delete_artifact(user_id=other, artifact_id=artifact_id):
                raise RuntimeError("Delete owner boundary failure")
        if len(remote.list_artifacts(user_id=owner)) != len(FORMATS):
            raise RuntimeError("Inventory mismatch")
        ok = True
    except Exception as exc:
        logger.warning("artifact_storage_canary status=FAIL error_type=%s", type(exc).__name__)
    finally:
        # Only exact IDs created in this invocation; never enumerate user data.
        for artifact_id in created:
            try:
                if not remote.delete_artifact(user_id=owner, artifact_id=artifact_id):
                    cleanup_ok = False
                if remote.read_artifact(user_id=owner, artifact_id=artifact_id) is not None:
                    cleanup_ok = False
            except Exception:
                cleanup_ok = False
        if not cleanup_ok:
            logger.warning("artifact_storage_canary cleanup=FAIL")
    if ok and cleanup_ok:
        logger.info(
            "artifact_storage_canary status=PASS formats=5 owner_namespace=PASS "
            "cleanup=PASS authenticated_e2e=not_tested restart=not_tested"
        )
        return True
    return False
