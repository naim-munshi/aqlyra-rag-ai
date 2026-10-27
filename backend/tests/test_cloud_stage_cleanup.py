"""Staging cleanup is operator-only, bounded, safe and dry-run by default."""
from datetime import timedelta
from sqlalchemy.orm import Session
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.services.cloud_stage_cleanup import cleanup_stale_staging
from app.services.cloud_document_finalization import (
    claim_with_reserved_final_key, finalize_cloud_upload,
)
from test_cloud_document_finalization import (
    InMemoryS3, configured, make_user, reserve,
)


def expire_intent(db: Session, intent_id: str):
    intent = db.get(CloudUploadIntent, intent_id)
    assert intent is not None
    intent.expires_at = utc_now_naive() - timedelta(hours=3)
    db.commit()


def test_complete_stage_swept_but_final_remains(client, db_session):
    owner, _ = make_user(client, db_session, "sweep_ok")
    store = InMemoryS3(b"data stays in final object")
    granted = reserve(db_session, owner, store)
    finished = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=granted.intent_id,
        cfg=configured(), client=store,
    )
    intent = db_session.get(CloudUploadIntent, granted.intent_id)
    staging_key = intent.object_key
    assert staging_key in store.objects
    expire_intent(db_session, granted.intent_id)

    dry = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store,
    )
    assert (dry.eligible, dry.deleted, dry.failed) == (1, 0, 0)
    assert staging_key in store.objects
    live = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert (live.eligible, live.deleted, live.failed) == (1, 1, 0)
    assert staging_key not in store.objects
    assert finished.final_object_key in store.objects
    assert db_session.get(CloudUploadIntent, granted.intent_id).stage_deleted_at
    again = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert again.eligible == 0 and again.deleted == 0


def test_expired_issued_can_be_cleaned_but_claimed_never_swept(
    client, db_session,
):
    owner, _ = make_user(client, db_session, "sweep_states")
    store = InMemoryS3()
    issued = reserve(db_session, owner, store)
    claimed = reserve(db_session, owner, store)
    confirmed = claim_with_reserved_final_key(
        db=db_session, owner=owner, intent_id=claimed.intent_id,
        cfg=configured(),
    )
    assert confirmed is not None
    expire_intent(db_session, issued.intent_id)
    expire_intent(db_session, claimed.intent_id)

    result = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert result.deleted == 1
    assert db_session.get(CloudUploadIntent, claimed.intent_id).stage_deleted_at is None
    assert db_session.get(CloudUploadIntent, issued.intent_id).stage_deleted_at is not None
    assert any(key == confirmed.object_key for key in store.objects)


def test_delete_failure_does_not_mark_record(client, db_session):
    owner, _ = make_user(client, db_session, "sweep_failure")
    store = InMemoryS3()
    issued = reserve(db_session, owner, store)
    expire_intent(db_session, issued.intent_id)

    def fail(**kwargs):
        raise RuntimeError("private-provider-error")

    original = store.delete_object
    store.delete_object = fail
    summary = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert summary.failed == 1 and summary.deleted == 0
    assert db_session.get(CloudUploadIntent, issued.intent_id).stage_deleted_at is None
    store.delete_object = original
    retry = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert retry.deleted == 1


def test_stale_cleanup_bounds_and_disabled_default(client, db_session):
    import pytest
    from app.services.private_object_storage import PrivateObjectStorageError

    owner, _ = make_user(client, db_session, "sweep_bounds")
    store = InMemoryS3()
    reserve(db_session, owner, store)
    with pytest.raises(ValueError):
        cleanup_stale_staging(db=db_session, cfg=configured(),
                              store=store, limit=1000)
    with pytest.raises(PrivateObjectStorageError):
        cleanup_stale_staging(
            db=db_session,
            cfg=configured(PRIVATE_OBJECT_STORAGE_ENABLED=False),
            store=store,
        )


def test_inconsistent_completed_record_is_not_swept(client, db_session):
    """A completed status without a durable Document link is not sufficient."""
    owner, _ = make_user(client, db_session, "sweep_inconsistent")
    store = InMemoryS3(b"data stays in final object")
    granted = reserve(db_session, owner, store)
    finished = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=granted.intent_id,
        cfg=configured(), client=store,
    )
    record = db_session.get(CloudUploadIntent, granted.intent_id)
    stage_key = record.object_key
    # Simulate an inconsistent legacy/partial state. Never delete stage
    # bytes while final-to-document linkage cannot be established.
    record.document_id = None
    db_session.commit()
    expire_intent(db_session, granted.intent_id)

    dry = cleanup_stale_staging(db=db_session, cfg=configured(), store=store)
    live = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert dry.eligible == 0
    assert (live.eligible, live.deleted, live.failed) == (0, 0, 0)
    assert stage_key in store.objects
    assert finished.final_object_key in store.objects
    assert db_session.get(CloudUploadIntent, granted.intent_id).stage_deleted_at is None


def test_issued_with_reserved_final_key_is_not_swept(client, db_session):
    """An inconsistent issued row may have recoverable object state."""
    owner, _ = make_user(client, db_session, "sweep_issued_reserved")
    store = InMemoryS3()
    granted = reserve(db_session, owner, store)
    record = db_session.get(CloudUploadIntent, granted.intent_id)
    stage_key = record.object_key
    record.final_object_key = "reserved-final-key-for-reconciliation"
    db_session.commit()
    expire_intent(db_session, granted.intent_id)

    result = cleanup_stale_staging(
        db=db_session, cfg=configured(), store=store, dry_run=False,
    )
    assert (result.eligible, result.deleted, result.failed) == (0, 0, 0)
    assert stage_key in store.objects
    assert db_session.get(CloudUploadIntent, granted.intent_id).stage_deleted_at is None
