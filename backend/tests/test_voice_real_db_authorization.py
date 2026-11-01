"""PostgreSQL-backed Voice Worker authorization regression.

Uses only the ephemeral CI test database (see conftest.py); no LiveKit
credentials, real audio, network calls, user files or production records.
"""
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.user import User
from app.voice.job_authorization import (
    VoiceJobAuthorizationError,
    authorize_voice_job,
)
from app.voice.job_metadata import VoiceJobData


@pytest.fixture
def two_voice_users(db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    discriminator = uuid4().hex
    alice = User(
        username=f"voice_a_{discriminator}",
        email=f"voice_a_{discriminator}@example.invalid",
        hashed_password="test-only-never-a-real-password",
        email_verified_at=datetime(2026, 1, 1),
        is_active=True,
    )
    bob = User(
        username=f"voice_b_{discriminator}",
        email=f"voice_b_{discriminator}@example.invalid",
        hashed_password="test-only-never-a-real-password",
        email_verified_at=datetime(2026, 1, 1),
        is_active=True,
    )
    db_session.add_all([alice, bob])
    db_session.flush()
    conversation_a = Conversation(user_id=alice.id, title="Private A", mode="knowledge")
    conversation_b = Conversation(user_id=bob.id, title="Private B", mode="knowledge")
    db_session.add_all([conversation_a, conversation_b])
    db_session.flush()

    def make_document(user_id: str, suffix: str):
        return Document(
            user_id=user_id,
            original_filename=f"{suffix}.txt",
            stored_filename=f"test-{suffix}.txt",
            storage_path=f"test-only/{suffix}.txt",
            content_type="text/plain",
            file_extension=".txt",
            file_size=1,
            checksum_sha256=uuid4().hex * 2,
            status="ready",
        )
    document_a = make_document(alice.id, "alice")
    document_b = make_document(bob.id, "bob")
    db_session.add_all([document_a, document_b])
    db_session.flush()
    return {
        "alice": alice, "bob": bob,
        "conversation_a": conversation_a, "conversation_b": conversation_b,
        "document_a": document_a, "document_b": document_b,
    }


def voice_job(*, user: User, conversation: Conversation, document: Document):
    return VoiceJobData(
        user_id=user.id,
        conversation_id=conversation.id,
        mode=conversation.mode,
        document_ids=(document.id,),
    )


def test_owner_can_use_owned_ready_document(db_session, two_voice_users):
    d = two_voice_users
    job = voice_job(
        user=d["alice"], conversation=d["conversation_a"],
        document=d["document_a"],
    )
    authorize_voice_job(db_session, job)


def test_foreign_conversation_denied_with_real_postgresql(db_session, two_voice_users):
    d = two_voice_users
    job = voice_job(
        user=d["alice"], conversation=d["conversation_b"],
        document=d["document_a"],
    )
    with pytest.raises(VoiceJobAuthorizationError, match="conversation"):
        authorize_voice_job(db_session, job)


def test_foreign_document_denied_with_real_postgresql(db_session, two_voice_users):
    d = two_voice_users
    job = voice_job(
        user=d["alice"], conversation=d["conversation_a"],
        document=d["document_b"],
    )
    with pytest.raises(VoiceJobAuthorizationError, match="document"):
        authorize_voice_job(db_session, job)


def test_account_revocation_denied_mid_call(db_session, two_voice_users):
    d = two_voice_users
    job = voice_job(
        user=d["alice"], conversation=d["conversation_a"],
        document=d["document_a"],
    )
    authorize_voice_job(db_session, job)
    d["alice"].is_active = False
    db_session.flush()
    with pytest.raises(VoiceJobAuthorizationError, match="identity"):
        authorize_voice_job(db_session, job)


def test_document_revocation_denied_mid_call(db_session, two_voice_users):
    d = two_voice_users
    job = voice_job(
        user=d["alice"], conversation=d["conversation_a"],
        document=d["document_a"],
    )
    authorize_voice_job(db_session, job)
    d["document_a"].status = "processing"
    db_session.flush()
    with pytest.raises(VoiceJobAuthorizationError, match="document"):
        authorize_voice_job(db_session, job)


def test_verification_revoked_denied(db_session, two_voice_users):
    d = two_voice_users
    job = voice_job(
        user=d["alice"], conversation=d["conversation_a"],
        document=d["document_a"],
    )
    d["alice"].email_verified_at = None
    db_session.flush()
    with pytest.raises(VoiceJobAuthorizationError, match="identity"):
        authorize_voice_job(db_session, job)
