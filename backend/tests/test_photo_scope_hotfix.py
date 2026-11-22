"""Regression for the production 'Selected documents must be processed and ready' photo bug."""
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

import app.api.conversations as conversations_api
from app.api.dependencies import get_current_user
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.services.chat_service import ChatExecutionResult


def _user(db: Session, suffix: str) -> User:
    user = User(
        email=f"photo-scope-{suffix}@example.org",
        username=f"photo-scope-{suffix}",
        hashed_password="test-only-hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _document(db: Session, owner: User, *, extension: str, status="uploaded") -> Document:
    mime = {".png": "image/png", ".jpg": "image/jpeg",
            ".webp": "image/webp", ".pdf": "application/pdf",
            ".txt": "text/plain"}[extension]
    doc = Document(
        user_id=str(owner.id),
        original_filename="photo" + extension,
        stored_filename=str(uuid4()) + extension,
        storage_path=f"cloud://documents/{owner.id}/{uuid4()}{extension}",
        content_type=mime, file_extension=extension,
        file_size=39, checksum_sha256=uuid4().hex * 2,
        status=status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _conversation(client: TestClient, user: User, *, mode="normal") -> str:
    app.dependency_overrides[get_current_user] = lambda: user
    response = client.post("/api/v1/conversations",
                           json={"title": "Photo analysis", "mode": mode})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _execute(**kwargs):
    return ChatExecutionResult(
        content="Photo understood.", mode="normal",
        provider_name="test-provider", model_name="test-model",
        response_id=None, citations=(), is_refusal=False,
        input_tokens=1, output_tokens=2, total_tokens=3,
        evidence_tokens=None,
    )


@pytest.fixture
def no_external_provider(monkeypatch):
    calls = []
    def execute(**kwargs):
        calls.append(kwargs["document_ids"])
        return _execute(**kwargs)
    monkeypatch.setattr(conversations_api, "execute_chat_turn", execute)
    monkeypatch.setattr(conversations_api, "extract_memories_best_effort",
                        lambda **kwargs: None)
    return calls


@pytest.mark.parametrize("extension", [".png", ".jpg", ".webp"])
@pytest.mark.parametrize("stream", [False, True])
def test_just_uploaded_photo_works_in_converse_without_indexing(
    client: TestClient, db_session: Session, no_external_provider,
    extension: str, stream: bool,
):
    owner = _user(db_session, f"allow-{extension[1:]}-{stream}")
    document = _document(db_session, owner, extension=extension)
    conversation = _conversation(client, owner)
    path = f"/api/v1/conversations/{conversation}/messages"
    response = client.post(path + ("/stream" if stream else ""), json={
        "content": "Explain it", "document_ids": [document.id],
    })
    assert response.status_code == 200
    assert "Photo understood." in response.text
    assert no_external_provider == [(document.id,)]
    assert "Selected documents must be processed and ready" not in response.text


@pytest.mark.parametrize("extension", [".pdf", ".txt"])
@pytest.mark.parametrize("stream", [False, True])
def test_unindexed_non_image_files_remain_blocked(
    client: TestClient, db_session: Session, no_external_provider,
    extension: str, stream: bool,
):
    owner = _user(db_session, f"block-{extension[1:]}-{stream}")
    doc = _document(db_session, owner, extension=extension)
    conversation = _conversation(client, owner)
    response = client.post(
        f"/api/v1/conversations/{conversation}/messages" + ("/stream" if stream else ""),
        json={"content": "Explain the document", "document_ids": [doc.id]},
    )
    assert response.status_code == (200 if stream else 422)
    assert "Selected documents must be processed and ready" in response.text
    assert not no_external_provider


@pytest.mark.parametrize("stream", [False, True])
def test_other_users_uploaded_photo_rejected_before_ai_or_persistence(
    client: TestClient, db_session: Session, no_external_provider, stream: bool,
):
    owner = _user(db_session, f"owner-{stream}")
    intruder = _user(db_session, f"intruder-{stream}")
    doc = _document(db_session, owner, extension=".png")
    conversation = _conversation(client, intruder)
    response = client.post(
        f"/api/v1/conversations/{conversation}/messages" + ("/stream" if stream else ""),
        json={"content": "Read this", "document_ids": [doc.id]},
    )
    assert response.status_code == (200 if stream else 422)
    assert "not available" in response.text
    assert not no_external_provider
    messages = client.get(f"/api/v1/conversations/{conversation}/messages")
    assert messages.json() == []


def test_unindexed_photo_not_accepted_in_knowledge(
    client: TestClient, db_session: Session, no_external_provider,
):
    owner = _user(db_session, "knowledge")
    doc = _document(db_session, owner, extension=".png")
    conversation = _conversation(client, owner, mode="knowledge")
    response = client.post(f"/api/v1/conversations/{conversation}/messages", json={
        "content": "Grounded search", "document_ids": [doc.id],
    })
    assert response.status_code == 422
    assert not no_external_provider


@pytest.mark.parametrize("stream", [False, True])
def test_multiple_unindexed_images_rejected_without_multipage_vision(
    client: TestClient, db_session: Session, no_external_provider, stream: bool,
):
    owner = _user(db_session, f"multi-{stream}")
    docs = [_document(db_session, owner, extension=".png") for _ in range(2)]
    conversation = _conversation(client, owner)
    response = client.post(
        f"/api/v1/conversations/{conversation}/messages" + ("/stream" if stream else ""),
        json={"content": "Explain both", "document_ids": [d.id for d in docs]},
    )
    assert response.status_code == (200 if stream else 422)
    assert "processed and ready" in response.text
    assert not no_external_provider
