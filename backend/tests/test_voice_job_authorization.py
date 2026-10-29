"""No real LiveKit credentials or audio needed for authorization checks."""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config.settings import settings
from app.voice.job_metadata import VoiceJobData
from app.voice import job_authorization as auth


def make_job(documents=()):
    return VoiceJobData(
        user_id=str(uuid4()),
        conversation_id=str(uuid4()),
        mode="knowledge",
        document_ids=tuple(documents),
    )


def setup_valid(monkeypatch, db, job):
    db.user = SimpleNamespace(is_active=True, email_verified_at=datetime(2026, 1, 1))
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr(
        auth, "get_conversation_for_user",
        lambda **kwargs: SimpleNamespace(mode=job.mode),
    )
    monkeypatch.setattr(
        auth, "get_user_document",
        lambda **kwargs: SimpleNamespace(status="ready"),
    )


class FakeDb:
    def __init__(self):
        self.user = None
    def get(self, model, identity):
        assert model.__name__ == "User"
        return self.user


def test_authorized_active_verified_user_and_owned_ready_scope(monkeypatch):
    job = make_job([str(uuid4())])
    db = FakeDb()
    setup_valid(monkeypatch, db, job)
    def resolve_conversation(**kwargs):
        assert kwargs["user_id"] == job.user_id
        assert kwargs["conversation_id"] == job.conversation_id
        return SimpleNamespace(mode=job.mode)
    def get_owned_doc(**kwargs):
        assert kwargs["user_id"] == job.user_id
        assert kwargs["document_id"] == job.document_ids[0]
        return SimpleNamespace(status="ready")
    monkeypatch.setattr(auth, "get_conversation_for_user", resolve_conversation)
    monkeypatch.setattr(auth, "get_user_document", get_owned_doc)
    auth.authorize_voice_job(db, job)


@pytest.mark.parametrize("account", [
    None,
    SimpleNamespace(is_active=False, email_verified_at=datetime(2026, 1, 1)),
    SimpleNamespace(is_active=True, email_verified_at=None),
])
def test_deleted_disabled_or_unverified_account_denied(monkeypatch, account):
    job = make_job()
    db = FakeDb()
    setup_valid(monkeypatch, db, job)
    db.user = account
    with pytest.raises(auth.VoiceJobAuthorizationError, match="no longer authorized"):
        auth.authorize_voice_job(db, job)


@pytest.mark.parametrize("conversation", [None, SimpleNamespace(mode="normal")])
def test_deleted_foreign_or_wrong_mode_conversation_denied(monkeypatch, conversation):
    job = make_job()
    db = FakeDb()
    setup_valid(monkeypatch, db, job)
    monkeypatch.setattr(auth, "get_conversation_for_user", lambda **_: conversation)
    with pytest.raises(auth.VoiceJobAuthorizationError, match="no longer available"):
        auth.authorize_voice_job(db, job)


@pytest.mark.parametrize("document", [None, SimpleNamespace(status="processing"), SimpleNamespace(status="failed")])
def test_foreign_deleted_or_unready_documents_denied(monkeypatch, document):
    job = make_job([str(uuid4())])
    db = FakeDb()
    setup_valid(monkeypatch, db, job)
    monkeypatch.setattr(auth, "get_user_document", lambda **_: document)
    with pytest.raises(auth.VoiceJobAuthorizationError, match="document scope"):
        auth.authorize_voice_job(db, job)


def test_worker_checks_at_start_and_before_each_rag_or_persist_turn():
    from pathlib import Path
    worker_source = (Path(__file__).parents[1] / "app" / "voice" / "worker.py").read_text()
    assert "await asyncio.to_thread(authorize_initial_job)" in worker_source
    assert worker_source.count("authorize_voice_job(db, self._job_data)") == 2
    assert '"user_id": job_data.user_id' not in worker_source
