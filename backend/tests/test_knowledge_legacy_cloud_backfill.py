"""Bounded, tenant-safe recovery of legacy finalized knowledge uploads."""
from datetime import timedelta
from uuid import uuid4

from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.user import User
from app.services.knowledge_index_queue import requeue_verified_legacy_cloud_documents


def _create(db, label, ext=".pdf", completed=True):
    user = User(
        username=f"backfill_{label}",
        email=f"backfill_{label}@example.org",
        hashed_password="test-only",
    )
    db.add(user)
    db.flush()
    digest = uuid4().hex * 2
    key = f"documents/{user.id}/{uuid4().hex}{ext}"
    doc = Document(
        user_id=str(user.id),
        original_filename=f"upload{ext}",
        stored_filename=f"{uuid4().hex}{ext}",
        storage_path="cloud://" + key,
        content_type="application/pdf" if ext == ".pdf" else "image/png",
        file_extension=ext, file_size=3, checksum_sha256=digest,
        status="uploaded",
    )
    db.add(doc)
    db.flush()
    if completed:
        db.add(CloudUploadIntent(
            user_id=str(user.id),
            object_key=f"staging/{user.id}/{uuid4().hex}",
            original_filename=doc.original_filename,
            content_type=doc.content_type,
            expected_size=3,
            expected_sha256=digest,
            status="completed",
            expires_at=utc_now_naive() + timedelta(hours=2),
            completed_at=utc_now_naive(),
            final_object_key=key,
            document_id=doc.id,
        ))
    db.commit()
    return doc


def test_requeues_only_completed_cloud_document(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_AUTO_INDEX_ENABLED", True)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    ready = _create(db_session, "ready_pdf")
    orphan = _create(db_session, "orphan_pdf", completed=False)
    image = _create(db_session, "image", ext=".png")
    assert requeue_verified_legacy_cloud_documents(db_session, limit=10) == 1
    db_session.refresh(ready)
    db_session.refresh(orphan)
    db_session.refresh(image)
    assert ready.status == "queued"
    assert orphan.status == "uploaded"
    assert image.status == "uploaded"
    assert requeue_verified_legacy_cloud_documents(db_session) == 0


def test_backfill_requires_feature_gates(db_session, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_AUTO_INDEX_ENABLED", False)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    _create(db_session, "disabled")
    assert requeue_verified_legacy_cloud_documents(db_session) == 0
    monkeypatch.setattr(settings, "KNOWLEDGE_AUTO_INDEX_ENABLED", True)
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", False)
    assert requeue_verified_legacy_cloud_documents(db_session) == 0
