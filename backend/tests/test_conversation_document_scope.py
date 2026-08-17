from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.api.conversations as conversations_api

from app.api.dependencies import get_current_user
from app.main import app
from app.models.conversation_document import (
    ConversationDocument,
)
from app.models.document import Document
from app.models.user import User
from app.services.chat_service import (
    ChatExecutionResult,
)


def create_user(
    db: Session,
    *,
    suffix: str,
) -> User:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        hashed_password="test-password-hash",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_as(
    user: User,
) -> None:
    app.dependency_overrides[
        get_current_user
    ] = lambda: user


def create_document(
    db: Session,
    *,
    user: User,
    suffix: str,
    status: str = "ready",
) -> Document:
    document = Document(
        user_id=str(user.id),
        original_filename=f"{suffix}.txt",
        stored_filename=f"{suffix}.txt",
        storage_path=f"tests/{suffix}.txt",
        content_type="text/plain",
        file_extension=".txt",
        file_size=20,
        checksum_sha256=(
            suffix.ljust(64, "0")[:64]
        ),
        status=status,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def create_knowledge_conversation(
    client: TestClient,
) -> str:
    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Scoped knowledge",
            "mode": "knowledge",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def fake_result() -> ChatExecutionResult:
    return ChatExecutionResult(
        content="Scoped answer.",
        mode="knowledge",
        provider_name="scope-test",
        model_name="scope-test-v1",
        response_id="scope-response",
        citations=(),
        is_refusal=False,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        evidence_tokens=8,
    )


def get_scope_ids(
    db: Session,
    *,
    conversation_id: str,
) -> tuple[str, ...]:
    statement = (
        select(
            ConversationDocument.document_id
        )
        .where(
            ConversationDocument.conversation_id
            == conversation_id
        )
        .order_by(
            ConversationDocument.created_at.asc(),
            ConversationDocument.document_id.asc(),
        )
    )

    return tuple(
        db.scalars(statement).all()
    )


def test_knowledge_scope_persists_and_is_reused(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-owner",
    )

    document = create_document(
        db_session,
        user=user,
        suffix="scope-doc-one",
    )

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    captured: list[
        tuple[str, ...]
    ] = []

    def execute(**kwargs):
        captured.append(
            tuple(kwargs["document_ids"])
        )

        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    first = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "First question",
            "document_ids": [
                document.id,
            ],
        },
    )

    assert first.status_code == 200

    assert captured[-1] == (
        document.id,
    )

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == (
        document.id,
    )

    second = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Follow-up question",
            "document_ids": [],
        },
    )

    assert second.status_code == 200

    assert captured[-1] == (
        document.id,
    )

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == (
        document.id,
    )


def test_knowledge_scope_adds_new_documents(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-add-owner",
    )

    first_document = create_document(
        db_session,
        user=user,
        suffix="scope-add-one",
    )

    second_document = create_document(
        db_session,
        user=user,
        suffix="scope-add-two",
    )

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    captured: list[
        tuple[str, ...]
    ] = []

    def execute(**kwargs):
        captured.append(
            tuple(kwargs["document_ids"])
        )

        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    first = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use first",
            "document_ids": [
                first_document.id,
            ],
        },
    )

    assert first.status_code == 200

    second = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Also use second",
            "document_ids": [
                second_document.id,
            ],
        },
    )

    assert second.status_code == 200

    assert captured[-1] == (
        first_document.id,
        second_document.id,
    )

    third = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use the same scope",
        },
    )

    assert third.status_code == 200

    assert captured[-1] == (
        first_document.id,
        second_document.id,
    )

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == (
        first_document.id,
        second_document.id,
    )


def test_other_users_document_cannot_enter_scope(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    owner = create_user(
        db_session,
        suffix="scope-secure-owner",
    )

    other = create_user(
        db_session,
        suffix="scope-secure-other",
    )

    other_document = create_document(
        db_session,
        user=other,
        suffix="scope-secure-doc",
    )

    authenticate_as(owner)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    called = False

    def execute(**kwargs):
        nonlocal called
        called = True
        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Read this",
            "document_ids": [
                other_document.id,
            ],
        },
    )

    assert response.status_code == 422
    assert called is False

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == ()

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_failed_generation_does_not_persist_scope(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-failure-owner",
    )

    document = create_document(
        db_session,
        user=user,
        suffix="scope-failure-doc",
    )

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    def execute(**kwargs):
        raise RuntimeError(
            "simulated generation failure"
        )

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    try:
        client.post(
            (
                "/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            json={
                "content": "This fails",
                "document_ids": [
                    document.id,
                ],
            },
        )
    except RuntimeError:
        pass

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == ()

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []


def test_unready_document_cannot_enter_scope(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-unready-owner",
    )

    document = create_document(
        db_session,
        user=user,
        suffix="scope-unready-doc",
        status="uploaded",
    )

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    called = False

    def execute(**kwargs):
        nonlocal called
        called = True
        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use unready",
            "document_ids": [
                document.id,
            ],
        },
    )

    assert response.status_code == 422
    assert called is False

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == ()


def test_duplicate_document_ids_are_rejected(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-duplicate-owner",
    )

    document = create_document(
        db_session,
        user=user,
        suffix="scope-duplicate-doc",
    )

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    called = False

    def execute(**kwargs):
        nonlocal called
        called = True
        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use this document",
            "document_ids": [
                document.id,
                document.id,
            ],
        },
    )

    assert response.status_code == 422
    assert called is False

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == ()

    history = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert history.status_code == 200
    assert history.json() == []



def test_missing_document_cannot_enter_scope(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-missing-owner",
    )

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    called = False

    def execute(**kwargs):
        nonlocal called
        called = True
        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    response = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use missing document",
            "document_ids": [
                "missing-document-id",
            ],
        },
    )

    assert response.status_code == 422
    assert called is False

    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == ()


def test_knowledge_scope_rejects_document_51(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_user(
        db_session,
        suffix="scope-limit-owner",
    )

    documents = [
        create_document(
            db_session,
            user=user,
            suffix=f"scope-limit-{index:02d}",
        )
        for index in range(51)
    ]

    authenticate_as(user)

    conversation_id = (
        create_knowledge_conversation(
            client
        )
    )

    captured: list[
        tuple[str, ...]
    ] = []

    def execute(**kwargs):
        captured.append(
            tuple(kwargs["document_ids"])
        )
        return fake_result()

    monkeypatch.setattr(
        conversations_api,
        "execute_chat_turn",
        execute,
    )

    first = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Use first fifty",
            "document_ids": [
                document.id
                for document in documents[:50]
            ],
        },
    )

    assert first.status_code == 200
    assert len(captured) == 1
    assert len(captured[0]) == 50

    stored_scope = get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    )

    assert len(stored_scope) == 50

    second = client.post(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "content": "Add one more",
            "document_ids": [
                documents[50].id,
            ],
        },
    )

    assert second.status_code == 422

    # Generation must not run for the rejected request.
    assert len(captured) == 1

    # Existing valid scope must remain unchanged.
    assert get_scope_ids(
        db_session,
        conversation_id=conversation_id,
    ) == stored_scope
