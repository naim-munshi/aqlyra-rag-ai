"""Recovery is explicit, owner-scoped, and never deletes a cloud object."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.main import app
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.user import User
import app.api.cloud_uploads as cloud_api


def _owner(label):
    return User(
        id=str(uuid4()),
        email=f"recovery-{label}-{uuid4().hex[:8]}@example.com",
        username=f"recovery_{label}_{uuid4().hex[:8]}",
        hashed_password="test-only", is_active=True,
        email_verified_at=utc_now_naive(),
    )


def _stale_intent(owner):
    return CloudUploadIntent(
        id=str(uuid4()), user_id=owner.id,
        original_filename="hello.txt", content_type="text/plain",
        object_key=f"documents/{owner.id}/{uuid4()}.txt",
        final_object_key=f"final/documents/{owner.id}/{uuid4()}.txt",
        expected_size=5, expected_sha256="f" * 64,
        status="claimed", expires_at=utc_now_naive() - timedelta(minutes=5),
        created_at=utc_now_naive() - timedelta(minutes=11),
        claimed_at=utc_now_naive() - timedelta(minutes=10),
    )


def test_only_owner_stale_claim_is_attempted(client, db_session, monkeypatch):
    owner, other = _owner("owner"), _owner("other")
    db_session.add_all((owner, other))
    db_session.flush()
    mine, theirs = _stale_intent(owner), _stale_intent(other)
    db_session.add_all((mine, theirs))
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", True)
    attempted = []

    def fake_recover(*, db, owner, intent_id):
        attempted.append((owner.id, intent_id))
        return SimpleNamespace(document_id="not-persisted")

    monkeypatch.setattr(cloud_api, "recover_promoted_cloud_document", fake_recover)
    monkeypatch.setattr(cloud_api, "get_user_document", lambda **kwargs: None)
    result = client.post("/api/v1/documents/cloud/recover")
    assert result.status_code == 200
    data = result.json()
    assert data["attempted"] == 1
    assert data["failed"] == 1
    assert attempted == [(owner.id, mine.id)]
    db_session.expire_all()
    assert db_session.get(CloudUploadIntent, theirs.id).status == "claimed"
    assert db_session.get(CloudUploadIntent, mine.id).status == "claimed"


def test_recovery_off_by_default(client, db_session, monkeypatch):
    owner = _owner("disabled")
    db_session.add(owner)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", False)
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", False)
    response = client.post("/api/v1/documents/cloud/recover")
    assert response.status_code == 503


def test_recovery_denied_for_unverified_owner(client, db_session, monkeypatch):
    owner = _owner("unverified")
    owner.email_verified_at = None
    db_session.add(owner)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", True)
    response = client.post("/api/v1/documents/cloud/recover")
    assert response.status_code == 403


def test_no_replay_of_recent_claim(client, db_session, monkeypatch):
    owner = _owner("recent")
    db_session.add(owner)
    db_session.flush()
    record = _stale_intent(owner)
    record.claimed_at = utc_now_naive()
    db_session.add(record)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_UPLOAD_PROXY_ENABLED", True)
    monkeypatch.setattr(
        cloud_api, "recover_promoted_cloud_document",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("In-flight finalization must not be touched")
        ),
    )
    response = client.post("/api/v1/documents/cloud/recover")
    assert response.status_code == 200
    assert response.json() == {"recovered": [], "attempted": 0, "failed": 0}
