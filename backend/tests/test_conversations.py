from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User


def create_user(
    db: Session,
    *,
    email: str,
    username: str,
) -> User:
    user = User(
        email=email,
        username=username,
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


def test_conversation_crud(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
    )

    authenticate_as(user)

    create_response = client.post(
        "/api/v1/conversations",
        json={
            "title": "  Research   chat  ",
            "mode": "knowledge",
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()

    assert created["title"] == "Research chat"
    assert created["mode"] == "knowledge"

    conversation_id = created["id"]

    list_response = client.get(
        "/api/v1/conversations"
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert (
        list_response.json()[0]["id"]
        == conversation_id
    )

    get_response = client.get(
        f"/api/v1/conversations/"
        f"{conversation_id}"
    )

    assert get_response.status_code == 200
    assert (
        get_response.json()["title"]
        == "Research chat"
    )

    update_response = client.patch(
        f"/api/v1/conversations/"
        f"{conversation_id}",
        json={
            "title": "General discussion",
            "mode": "normal",
        },
    )

    assert update_response.status_code == 200
    assert (
        update_response.json()["title"]
        == "General discussion"
    )
    assert (
        update_response.json()["mode"]
        == "normal"
    )

    delete_response = client.delete(
        f"/api/v1/conversations/"
        f"{conversation_id}"
    )

    assert delete_response.status_code == 204

    missing_response = client.get(
        f"/api/v1/conversations/"
        f"{conversation_id}"
    )

    assert missing_response.status_code == 404


def test_conversation_owner_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        email="owner2@example.com",
        username="owner2",
    )

    other = create_user(
        db_session,
        email="other@example.com",
        username="other",
    )

    authenticate_as(owner)

    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Private conversation",
            "mode": "knowledge",
        },
    )

    assert response.status_code == 201

    conversation_id = response.json()["id"]

    authenticate_as(other)

    get_response = client.get(
        f"/api/v1/conversations/"
        f"{conversation_id}"
    )

    assert get_response.status_code == 404

    patch_response = client.patch(
        f"/api/v1/conversations/"
        f"{conversation_id}",
        json={
            "title": "Unauthorized",
        },
    )

    assert patch_response.status_code == 404

    delete_response = client.delete(
        f"/api/v1/conversations/"
        f"{conversation_id}"
    )

    assert delete_response.status_code == 404

    list_response = client.get(
        "/api/v1/conversations"
    )

    assert list_response.status_code == 200
    assert list_response.json() == []


def test_conversation_validation(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="validation@example.com",
        username="validation",
    )

    authenticate_as(user)

    invalid_mode = client.post(
        "/api/v1/conversations",
        json={
            "title": "Invalid",
            "mode": "other",
        },
    )

    assert invalid_mode.status_code == 422

    blank_title = client.post(
        "/api/v1/conversations",
        json={
            "title": "   ",
            "mode": "normal",
        },
    )

    assert blank_title.status_code == 422

    empty_update = client.patch(
        "/api/v1/conversations/not-found",
        json={},
    )

    assert empty_update.status_code == 422


def test_conversation_pin_unpin_and_ordering(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="pin-owner@example.com",
        username="pin-owner",
    )

    authenticate_as(user)

    first_response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Pinned conversation",
            "mode": "normal",
        },
    )

    assert first_response.status_code == 201

    first = first_response.json()

    assert first["is_pinned"] is False

    first_id = first["id"]

    pin_response = client.patch(
        f"/api/v1/conversations/{first_id}",
        json={
            "is_pinned": True,
        },
    )

    assert pin_response.status_code == 200
    assert (
        pin_response.json()["is_pinned"]
        is True
    )

    second_response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Newer unpinned conversation",
            "mode": "normal",
        },
    )

    assert second_response.status_code == 201

    second = second_response.json()

    assert second["is_pinned"] is False

    list_response = client.get(
        "/api/v1/conversations"
    )

    assert list_response.status_code == 200

    conversations = list_response.json()

    assert len(conversations) == 2
    assert conversations[0]["id"] == first_id
    assert conversations[0]["is_pinned"] is True
    assert (
        conversations[1]["id"]
        == second["id"]
    )
    assert (
        conversations[1]["is_pinned"]
        is False
    )

    rename_response = client.patch(
        f"/api/v1/conversations/{first_id}",
        json={
            "title": "Renamed pinned chat",
        },
    )

    assert rename_response.status_code == 200
    assert (
        rename_response.json()["title"]
        == "Renamed pinned chat"
    )
    assert (
        rename_response.json()["is_pinned"]
        is True
    )

    unpin_response = client.patch(
        f"/api/v1/conversations/{first_id}",
        json={
            "is_pinned": False,
        },
    )

    assert unpin_response.status_code == 200
    assert (
        unpin_response.json()["is_pinned"]
        is False
    )


def test_conversation_pin_owner_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        email="pin-owner2@example.com",
        username="pin-owner2",
    )

    other = create_user(
        db_session,
        email="pin-other@example.com",
        username="pin-other",
    )

    authenticate_as(owner)

    create_response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Owner pinned chat",
            "mode": "normal",
        },
    )

    assert create_response.status_code == 201

    conversation_id = (
        create_response.json()["id"]
    )

    authenticate_as(other)

    response = client.patch(
        f"/api/v1/conversations/"
        f"{conversation_id}",
        json={
            "is_pinned": True,
        },
    )

    assert response.status_code == 404
