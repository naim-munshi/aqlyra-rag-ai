"""Database-backed cloud upload intents: verified owner, TTL and replay denial."""
import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.datetime_utils import utc_now_naive
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.user import User
from app.services.cloud_upload_intent_service import (
    claim_upload_intent,
    complete_upload_intent,
    fail_upload_intent,
    reserve_upload_intent,
)
from app.services.private_object_storage import PrivateObjectStorageError


class FakeStorage:
    def __init__(self):
        self.params = []

    def generate_presigned_url(self, method, **kwargs):
        self.params.append((method, kwargs))
        p = kwargs["Params"]
        return (
            "https://br-private-example.storage.c-2.us-east-2.aws.neon.tech/"
            + p["Bucket"] + "/" + p["Key"] + "?X-Amz-Signature=fake"
        )


def storage_settings(**changes):
    values = {
        "PRIVATE_OBJECT_STORAGE_ENABLED": True,
        "AWS_ENDPOINT_URL_S3": (
            "https://br-private-example.storage.c-2.us-east-2.aws.neon.tech"
        ),
        "AWS_REGION": "us-east-2",
        "AWS_ACCESS_KEY_ID": "private-test-access",
        "AWS_SECRET_ACCESS_KEY": "private-test-secret",
        "OBJECT_STORAGE_BUCKET": "private-documents",
    }
    values.update(changes)
    return Settings(_env_file=None, **values)


def create_verified_user(client, db: Session, label: str) -> User:
    unique = uuid4().hex[:9]
    data = {
        "username": f"storage_{label}_{unique}",
        "email": f"storage_{label}_{unique}@example.com",
        "password": "SafeTestPass123!",
    }
    result = client.post("/api/v1/auth/register", json=data)
    assert result.status_code == 201, result.text
    user = db.scalar(select(User).where(User.email == data["email"]))
    assert user is not None
    assert user.email_verified_at is not None
    return user


def reserve(db, user, *, fake=None):
    return reserve_upload_intent(
        db=db, owner=user, original_filename="project.txt",
        expected_size=5,
        expected_sha256=hashlib.sha256(b"hello").hexdigest(),
        cfg=storage_settings(), client=fake or FakeStorage(),
    )


def test_persistent_upload_intent_has_short_lived_signed_grant(
    client, db_session,
):
    owner = create_verified_user(client, db_session, "owner")
    fake = FakeStorage()
    grant = reserve(db_session, owner, fake=fake)
    assert grant.grant.expires_in_seconds == 120
    assert "documents/" + owner.id + "/" in grant.grant.key
    assert grant.expires_at > utc_now_naive()
    assert len(fake.params) == 1
    persisted = db_session.get(CloudUploadIntent, grant.intent_id)
    assert persisted is not None
    assert persisted.user_id == owner.id
    assert persisted.object_key == grant.grant.key
    assert persisted.status == "issued"
    assert persisted.expected_sha256 == hashlib.sha256(b"hello").hexdigest()
    assert "Signature" not in persisted.object_key
    assert "private-test-secret" not in repr(persisted)


def test_only_owner_can_claim_and_replay_fails(client, db_session):
    owner = create_verified_user(client, db_session, "owner")
    other = create_verified_user(client, db_session, "other")
    grant = reserve(db_session, owner)

    assert claim_upload_intent(
        db=db_session, owner=other, intent_id=grant.intent_id,
    ) is None
    result = claim_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    )
    assert result is not None
    assert result.status == "claimed"
    assert claim_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is None
    assert complete_upload_intent(
        db=db_session, owner=other, intent_id=grant.intent_id,
    ) is None
    # Legacy nontransactional completion MUST NOT bypass verified
    # final-object and Document linkage.
    complete = complete_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    )
    assert complete is None
    persisted = db_session.get(CloudUploadIntent, grant.intent_id)
    assert persisted is not None
    assert persisted.status == "claimed"
    assert persisted.completed_at is None
    assert persisted.document_id is None
    assert complete_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is None
    failed = fail_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    )
    assert failed is not None and failed.status == "failed"
    assert fail_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is None


def test_expired_intent_cannot_be_claimed(client, db_session):
    owner = create_verified_user(client, db_session, "owner")
    grant = reserve(db_session, owner)
    pending = db_session.get(CloudUploadIntent, grant.intent_id)
    assert pending is not None
    pending.expires_at = utc_now_naive() - timedelta(seconds=1)
    db_session.commit()
    assert claim_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is None


def test_invalid_or_missing_intent_identifiers_return_none(client, db_session):
    owner = create_verified_user(client, db_session, "owner")
    for id_value in ("../../etc/passwd", "not-an-id", str(uuid4())):
        assert claim_upload_intent(
            db=db_session, owner=owner, intent_id=id_value,
        ) is None
        assert complete_upload_intent(
            db=db_session, owner=owner, intent_id=id_value,
        ) is None


def test_failed_claim_cannot_be_completed(client, db_session):
    owner = create_verified_user(client, db_session, "owner")
    grant = reserve(db_session, owner)
    assert complete_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is None
    assert claim_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is not None
    failed = fail_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    )
    assert failed is not None
    assert failed.status == "failed"
    assert claim_upload_intent(
        db=db_session, owner=owner, intent_id=grant.intent_id,
    ) is None


@pytest.mark.parametrize("bad_digest", ["ABC", "f" * 63, "x" * 64, "F" * 64])
def test_bad_checksum_never_creates_intent(client, db_session, bad_digest):
    owner = create_verified_user(client, db_session, "owner")
    with pytest.raises(PrivateObjectStorageError, match="SHA-256"):
        reserve_upload_intent(
            db=db_session, owner=owner, original_filename="hello.txt",
            expected_size=5, expected_sha256=bad_digest,
            cfg=storage_settings(), client=FakeStorage(),
        )
    assert db_session.query(CloudUploadIntent).count() == 0


def test_unverified_and_inactive_users_are_denied(client, db_session):
    owner = create_verified_user(client, db_session, "owner")
    owner.email_verified_at = None
    db_session.flush()
    with pytest.raises(PrivateObjectStorageError, match="Verified"):
        reserve(db_session, owner)
    owner.email_verified_at = utc_now_naive()
    owner.is_active = False
    db_session.flush()
    with pytest.raises(PrivateObjectStorageError, match="Verified"):
        reserve(db_session, owner)
    assert db_session.query(CloudUploadIntent).count() == 0


def test_feature_stays_disabled_for_old_local_storage(client, db_session):
    owner = create_verified_user(client, db_session, "owner")
    disabled = storage_settings(PRIVATE_OBJECT_STORAGE_ENABLED=False)
    with pytest.raises(PrivateObjectStorageError, match="disabled"):
        reserve_upload_intent(
            db=db_session, owner=owner, original_filename="hello.txt",
            expected_size=5, expected_sha256=hashlib.sha256(b"hello").hexdigest(),
            cfg=disabled, client=FakeStorage(),
        )
    assert db_session.query(CloudUploadIntent).count() == 0
