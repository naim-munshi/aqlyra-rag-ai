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


def authenticate_as(user: User) -> None:
    app.dependency_overrides[
        get_current_user
    ] = lambda: user


def create_project(
    client: TestClient,
    *,
    name: str,
    mode: str,
) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "mode": mode},
    )
    assert response.status_code == 201
    return response.json()


def create_conversation(
    client: TestClient,
    *,
    title: str,
    mode: str,
) -> dict:
    response = client.post(
        "/api/v1/conversations",
        json={"title": title, "mode": mode},
    )
    assert response.status_code == 201
    return response.json()


def test_project_crud_and_mode_filter(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="project-owner@example.com",
        username="project-owner",
    )
    authenticate_as(user)

    normal = create_project(
        client,
        name="  Product   Ideas ",
        mode="normal",
    )
    knowledge = create_project(
        client,
        name="Research",
        mode="knowledge",
    )

    assert normal["name"] == "Product Ideas"
    assert normal["mode"] == "normal"
    assert knowledge["mode"] == "knowledge"

    normal_list = client.get(
        "/api/v1/projects?mode=normal"
    )
    assert normal_list.status_code == 200
    assert [
        item["id"]
        for item in normal_list.json()
    ] == [normal["id"]]

    rename = client.patch(
        f"/api/v1/projects/{normal['id']}",
        json={"name": "Product Planning"},
    )
    assert rename.status_code == 200
    assert rename.json()["name"] == "Product Planning"

    delete = client.delete(
        f"/api/v1/projects/{knowledge['id']}"
    )
    assert delete.status_code == 204


def test_project_owner_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        email="project-owner2@example.com",
        username="project-owner2",
    )
    other = create_user(
        db_session,
        email="project-other@example.com",
        username="project-other",
    )

    authenticate_as(owner)
    project = create_project(
        client,
        name="Private project",
        mode="normal",
    )

    authenticate_as(other)

    assert client.get(
        f"/api/v1/projects/{project['id']}"
    ).status_code == 404

    assert client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Unauthorized"},
    ).status_code == 404

    assert client.delete(
        f"/api/v1/projects/{project['id']}"
    ).status_code == 404

    list_response = client.get(
        "/api/v1/projects"
    )
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_conversation_project_assignment(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="assign-owner@example.com",
        username="assign-owner",
    )
    authenticate_as(user)

    converse_project = create_project(
        client,
        name="Converse work",
        mode="normal",
    )
    knowledge_project = create_project(
        client,
        name="Knowledge work",
        mode="knowledge",
    )
    conversation = create_conversation(
        client,
        title="Regular chat",
        mode="normal",
    )

    assert conversation["project_id"] is None

    assign = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"project_id": converse_project["id"]},
    )
    assert assign.status_code == 200
    assert assign.json()["project_id"] == converse_project["id"]

    wrong_mode = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"project_id": knowledge_project["id"]},
    )
    assert wrong_mode.status_code == 422

    remove = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"project_id": None},
    )
    assert remove.status_code == 200
    assert remove.json()["project_id"] is None


def test_cross_user_project_assignment_is_hidden(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        email="hidden-owner@example.com",
        username="hidden-owner",
    )
    other = create_user(
        db_session,
        email="hidden-other@example.com",
        username="hidden-other",
    )

    authenticate_as(owner)
    private_project = create_project(
        client,
        name="Owner only",
        mode="normal",
    )

    authenticate_as(other)
    conversation = create_conversation(
        client,
        title="Other user chat",
        mode="normal",
    )

    response = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"project_id": private_project["id"]},
    )
    assert response.status_code == 404


def test_deleting_project_returns_chat_to_history(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="delete-project@example.com",
        username="delete-project",
    )
    authenticate_as(user)

    project = create_project(
        client,
        name="Temporary",
        mode="knowledge",
    )
    conversation = create_conversation(
        client,
        title="Grounded chat",
        mode="knowledge",
    )

    assign = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"project_id": project["id"]},
    )
    assert assign.status_code == 200

    delete = client.delete(
        f"/api/v1/projects/{project['id']}"
    )
    assert delete.status_code == 204

    get_response = client.get(
        f"/api/v1/conversations/{conversation['id']}"
    )
    assert get_response.status_code == 200
    assert get_response.json()["project_id"] is None


def test_mode_change_detaches_existing_project(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="mode-change@example.com",
        username="mode-change",
    )
    authenticate_as(user)

    project = create_project(
        client,
        name="Knowledge project",
        mode="knowledge",
    )
    conversation = create_conversation(
        client,
        title="Switch mode",
        mode="knowledge",
    )

    assign = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"project_id": project["id"]},
    )
    assert assign.status_code == 200

    switch = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"mode": "normal"},
    )
    assert switch.status_code == 200
    assert switch.json()["mode"] == "normal"
    assert switch.json()["project_id"] is None


def test_create_conversation_directly_in_project(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="direct-project@example.com",
        username="direct-project",
    )
    authenticate_as(user)

    project = create_project(
        client,
        name="Direct project",
        mode="normal",
    )

    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Direct project chat",
            "mode": "normal",
            "project_id": project["id"],
        },
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == project["id"]


def test_direct_create_rejects_project_mode_mismatch(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="direct-mismatch@example.com",
        username="direct-mismatch",
    )
    authenticate_as(user)

    project = create_project(
        client,
        name="Knowledge only",
        mode="knowledge",
    )

    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Wrong mode",
            "mode": "normal",
            "project_id": project["id"],
        },
    )

    assert response.status_code == 422


def test_direct_create_hides_cross_user_project(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        email="direct-hidden-owner@example.com",
        username="direct-hidden-owner",
    )
    other = create_user(
        db_session,
        email="direct-hidden-other@example.com",
        username="direct-hidden-other",
    )

    authenticate_as(owner)
    project = create_project(
        client,
        name="Private direct project",
        mode="normal",
    )

    authenticate_as(other)
    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Unauthorized direct chat",
            "mode": "normal",
            "project_id": project["id"],
        },
    )

    assert response.status_code == 404
