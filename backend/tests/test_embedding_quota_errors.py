"""Quota failures must be actionable without inventing RAG evidence."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.conversations as conversation_api
import app.api.documents as document_api
from app.api.dependencies import get_current_user
from app.embeddings import EmbeddingProviderQuotaError, EmbeddingProviderRequestError
from app.embeddings.huggingface_provider import HuggingFaceEmbeddingProvider
from app.main import app
from app.models.conversation import Conversation
from app.models.user import User


class QuotaFailure(Exception):
    def __init__(self, status_code):
        self.response = SimpleNamespace(status_code=status_code)


class FakeQuotaClient:
    def __init__(self, status_code):
        self.status_code = status_code
    def feature_extraction(self, *args, **kwargs):
        raise QuotaFailure(self.status_code)


def test_huggingface_http_402_classified_as_quota():
    p = HuggingFaceEmbeddingProvider(token="", dimension=4, client=FakeQuotaClient(402))
    with pytest.raises(EmbeddingProviderQuotaError, match="quota"):
        p.embed_query("Hello")


def test_huggingface_other_failures_remain_generic():
    p = HuggingFaceEmbeddingProvider(token="", dimension=4, client=FakeQuotaClient(503))
    with pytest.raises(EmbeddingProviderRequestError) as err:
        p.embed_query("Hello")
    assert not isinstance(err.value, EmbeddingProviderQuotaError)


def test_chat_quota_error_is_503_and_does_not_persist_fake_answer(
    client: TestClient, db_session, monkeypatch,
):
    user = User(email="quota@example.com", username="quotatest", hashed_password="test")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    app.dependency_overrides[get_current_user] = lambda: user
    conversation = Conversation(user_id=str(user.id), title="Quota test", mode="knowledge")
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    def quota(**kwargs):
        raise EmbeddingProviderQuotaError("private provider billing error")

    monkeypatch.setattr(conversation_api, "execute_chat_turn", quota)
    result = client.post(
        "/api/v1/conversations/" + str(conversation.id) + "/messages",
        json={"content": "What does this document say?"},
    )
    assert result.status_code == 503
    assert "embedding service quota" in result.json()["detail"].lower()
    assert "private provider" not in result.text
    assert client.get(
        "/api/v1/conversations/" + str(conversation.id) + "/messages"
    ).json() == []


def test_document_processing_quota_is_retriable_and_not_generic_500(
    client: TestClient, db_session, monkeypatch,
):
    from app.models.document import Document

    owner = User(email="quota-doc@example.com", username="quotadoc", hashed_password="test")
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    app.dependency_overrides[get_current_user] = lambda: owner

    monkeypatch.setattr(document_api, "get_user_document", lambda **_: SimpleNamespace(
        storage_path="local://test-file"
    ))
    monkeypatch.setattr(
        document_api, "process_document",
        lambda **_: (_ for _ in ()).throw(EmbeddingProviderQuotaError("billing error")),
    )
    result = client.post("/api/v1/documents/" + str(uuid4()) + "/process")
    assert result.status_code == 503
    assert "quota" in result.json()["detail"].lower()
    assert "billing error" not in result.text


@pytest.mark.parametrize(
    ("failure", "expected_text"),
    [
        (EmbeddingProviderQuotaError("private Hugging Face billing URL"), "quota"),
        (EmbeddingProviderRequestError("private Hugging Face connection URL"), "temporarily unavailable"),
    ],
)
def test_grounded_ai_file_embedding_failure_is_sanitized_and_no_artifact_saved(
    client: TestClient, db_session, monkeypatch, failure, expected_text,
):
    import app.api.artifacts as artifact_api
    from app.config.settings import settings

    owner = User(
        email="quota-artifact@example.com",
        username="quotaartifact",
        hashed_password="test",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    app.dependency_overrides[get_current_user] = lambda: owner
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(
        artifact_api, "get_user_document",
        lambda **_: SimpleNamespace(status="ready"),
    )
    def fail_retrieval(**kwargs):
        raise failure
    def no_file_written(**kwargs):
        raise AssertionError("No artifact must be saved on embedding failure")
    monkeypatch.setattr(artifact_api, "answer_question", fail_retrieval)
    monkeypatch.setattr(artifact_api, "create_artifact", no_file_written)

    response = client.post(
        "/api/v1/artifacts/generate",
        json={
            "title": "Grounded evidence",
            "format": "pdf",
            "prompt": "Generate a grounded report about the source.",
            "document_ids": [str(uuid4())],
            "confirm_share_documents": True,
        },
    )
    assert response.status_code == 503
    assert expected_text in response.json()["detail"].lower()
    assert "private Hugging Face" not in response.text
    assert "file" in response.json()["detail"].lower()
