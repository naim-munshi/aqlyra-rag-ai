import hashlib
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.main import app
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
)
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.user import User


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
    user_id = str(user.id)

    def override_current_user():
        return SimpleNamespace(
            id=user_id,
        )

    app.dependency_overrides[
        get_current_user
    ] = override_current_user


def create_memory_via_api(
    client: TestClient,
    *,
    kind: str = "preference",
    content: str = "I prefer dark mode.",
) -> dict:
    response = client.post(
        "/api/v1/memories",
        json={
            "kind": kind,
            "content": content,
            "importance": 0.8,
            "confidence": 0.95,
        },
    )

    assert response.status_code == 201

    return response.json()


def test_memory_endpoint_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/memories"
    )

    assert response.status_code == 401


def test_create_list_and_get_memory(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-api-owner",
    )

    authenticate_as(user)

    payload = create_memory_via_api(
        client,
        content=(
            "  I   prefer   dark mode.  "
        ),
    )

    assert payload["kind"] == "preference"
    assert payload["content"] == (
        "I prefer dark mode."
    )
    assert payload["importance"] == 0.8
    assert payload["confidence"] == 0.95
    assert payload["source_message_id"] is None
    assert payload["is_active"] is True

    assert "user_id" not in payload
    assert "normalized_content" not in payload
    assert "embeddings" not in payload

    memory = db_session.get(
        Memory,
        payload["id"],
    )

    assert memory is not None
    assert memory.user_id == user.id
    assert memory.normalized_content == (
        "i prefer dark mode."
    )

    list_response = client.get(
        "/api/v1/memories"
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(
        f"/api/v1/memories/{payload['id']}"
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == (
        payload["id"]
    )


def test_memory_filters_and_activation(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-filter-owner",
    )

    authenticate_as(user)

    preference = create_memory_via_api(
        client,
        kind="preference",
        content="I prefer Python.",
    )

    create_memory_via_api(
        client,
        kind="goal",
        content="I want to learn Rust.",
    )

    patch_response = client.patch(
        (
            "/api/v1/memories/"
            f"{preference['id']}"
        ),
        json={
            "is_active": False,
        },
    )

    assert patch_response.status_code == 200
    assert (
        patch_response.json()["is_active"]
        is False
    )

    inactive_response = client.get(
        "/api/v1/memories",
        params={
            "is_active": "false",
        },
    )

    assert inactive_response.status_code == 200
    assert [
        item["id"]
        for item in inactive_response.json()
    ] == [preference["id"]]

    goal_response = client.get(
        "/api/v1/memories",
        params={
            "kind": "goal",
        },
    )

    assert goal_response.status_code == 200
    assert len(goal_response.json()) == 1
    assert (
        goal_response.json()[0]["kind"]
        == "goal"
    )

    reactivate_response = client.patch(
        (
            "/api/v1/memories/"
            f"{preference['id']}"
        ),
        json={
            "is_active": True,
        },
    )

    assert (
        reactivate_response.status_code
        == 200
    )
    assert (
        reactivate_response.json()["is_active"]
        is True
    )


def test_content_update_invalidates_stale_embedding(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-reembed-owner",
    )

    authenticate_as(user)

    payload = create_memory_via_api(
        client,
        content="I prefer Python.",
    )

    memory_id = payload["id"]

    old_content = payload["content"]

    embedding = MemoryEmbedding(
        memory_id=memory_id,
        provider_name="deterministic",
        model_name="deterministic-384",
        dimension=EMBEDDING_DIMENSION,
        embedding=[
            0.0
            for _ in range(
                EMBEDDING_DIMENSION
            )
        ],
        content_hash=hashlib.sha256(
            old_content.encode("utf-8")
        ).hexdigest(),
        input_token_count=4,
        estimated_cost_usd=0.0,
        embedding_metadata={},
    )

    db_session.add(embedding)
    db_session.commit()

    embedding_id = embedding.id

    response = client.patch(
        f"/api/v1/memories/{memory_id}",
        json={
            "content": "I prefer Rust.",
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == (
        "I prefer Rust."
    )

    db_session.expire_all()

    assert (
        db_session.get(
            MemoryEmbedding,
            embedding_id,
        )
        is None
    )

    memory = db_session.get(
        Memory,
        memory_id,
    )

    assert memory is not None
    assert memory.normalized_content == (
        "i prefer rust."
    )


def test_cross_user_memory_access_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        suffix="memory-private-owner",
    )

    attacker = create_user(
        db_session,
        suffix="memory-private-other",
    )

    authenticate_as(owner)

    payload = create_memory_via_api(
        client,
        content="My private preference.",
    )

    memory_id = payload["id"]

    authenticate_as(attacker)

    get_response = client.get(
        f"/api/v1/memories/{memory_id}"
    )

    assert get_response.status_code == 404

    patch_response = client.patch(
        f"/api/v1/memories/{memory_id}",
        json={
            "content": "Tampered memory",
        },
    )

    assert patch_response.status_code == 404

    delete_response = client.delete(
        f"/api/v1/memories/{memory_id}"
    )

    assert delete_response.status_code == 404

    memory = db_session.scalar(
        select(Memory).where(
            Memory.id == memory_id
        )
    )

    assert memory is not None
    assert memory.user_id == owner.id
    assert memory.content == (
        "My private preference."
    )


def test_delete_own_memory(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-delete-owner",
    )

    authenticate_as(user)

    payload = create_memory_via_api(
        client,
        content="Temporary memory.",
    )

    memory_id = payload["id"]

    response = client.delete(
        f"/api/v1/memories/{memory_id}"
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/memories/{memory_id}"
    )

    assert get_response.status_code == 404


def test_memory_api_rejects_invalid_or_internal_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        suffix="memory-validation-owner",
    )

    authenticate_as(user)

    invalid_kind = client.post(
        "/api/v1/memories",
        json={
            "kind": "secret",
            "content": "Invalid kind",
        },
    )

    assert invalid_kind.status_code == 422

    invalid_importance = client.post(
        "/api/v1/memories",
        json={
            "kind": "fact",
            "content": "Invalid importance",
            "importance": 1.5,
        },
    )

    assert (
        invalid_importance.status_code
        == 422
    )

    spoofed_internal = client.post(
        "/api/v1/memories",
        json={
            "kind": "fact",
            "content": "Attempt spoofing",
            "user_id": "another-user",
            "source_message_id": "message-id",
        },
    )

    assert (
        spoofed_internal.status_code
        == 422
    )

    payload = create_memory_via_api(
        client,
    )

    empty_patch = client.patch(
        (
            "/api/v1/memories/"
            f"{payload['id']}"
        ),
        json={},
    )

    assert empty_patch.status_code == 422
