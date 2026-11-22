"""Admin account inventory, verified-mailbox handoff, and safe mutations."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.config.settings import Settings, settings
from app.core.datetime_utils import utc_now_naive
from app.models.document import Document
from app.models.user import User


def add_user(db: Session, email: str, *, verified=True) -> tuple[User, str]:
    user = User(
        email=email,
        username="admin_mgmt_" + uuid4().hex[:14],
        hashed_password="synthetic-only",
        email_verified_at=utc_now_naive() if verified else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), token_version=user.auth_epoch)
    return user, token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def test_admin_mailbox_disabled_until_verification(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "aqlyra.verify@gmail.com")
    user, token = add_user(db_session, "aqlyra.verify@gmail.com", verified=False)

    assert client.get("/api/v1/users/me", headers=auth(token)).status_code == 200
    assert client.get("/api/v1/users/me", headers=auth(token)).json()["is_admin"] is False
    assert client.get("/api/v1/admin/users", headers=auth(token)).status_code == 403

    user.email_verified_at = utc_now_naive()
    db_session.commit()
    assert client.get("/api/v1/users/me", headers=auth(token)).json()["is_admin"] is True
    assert client.get("/api/v1/admin/users", headers=auth(token)).status_code == 200


def test_uuid_admin_continues_working_during_mailbox_transfer(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    owner, token = add_user(db_session, "previous_owner@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", owner.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "aqlyra.verify@gmail.com")
    assert client.get("/api/v1/admin/users", headers=auth(token)).status_code == 200


def test_admin_account_list_is_paged_and_not_public(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    owner, owner_token = add_user(db_session, "owner@example.com")
    other, other_token = add_user(db_session, "test.user@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", owner.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "")

    assert client.get("/api/v1/admin/users").status_code == 401
    assert client.get("/api/v1/admin/users", headers=auth(other_token)).status_code == 403
    response = client.get(
        "/api/v1/admin/users?limit=1&offset=0", headers=auth(owner_token)
    )
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private, no-store")
    assert response.json()["total"] == 2
    assert len(response.json()["users"]) == 1
    assert set(response.json()["users"][0]) == {
        "id", "email", "username", "is_active", "is_verified",
        "is_admin", "created_at",
    }
    assert "hashed_password" not in response.text
    assert "auth_epoch" not in response.text
    assert client.get(
        "/api/v1/admin/users?q=test.user%40example.com",
        headers=auth(owner_token),
    ).json()["total"] == 1
    assert client.get(
        "/api/v1/admin/users?q=%25", headers=auth(owner_token)
    ).json()["total"] == 0
    assert client.get(
        "/api/v1/admin/users?limit=1000", headers=auth(owner_token)
    ).status_code == 422


def test_admin_disables_reenables_and_revokes_old_sessions(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    owner, token = add_user(db_session, "operator@example.com")
    member, member_token = add_user(db_session, "member@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", owner.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "")

    path = f"/api/v1/admin/users/{member.id}/status"
    denied = client.patch(path, headers=auth(member_token),
                          json={"action": "disable", "confirm_email": member.email})
    assert denied.status_code == 403
    mismatched = client.patch(path, headers=auth(token),
                              json={"action": "disable", "confirm_email": "wrong@example.com"})
    assert mismatched.status_code == 409
    assert db_session.get(User, member.id).is_active is True

    disabled = client.patch(path, headers=auth(token),
                            json={"action": "disable", "confirm_email": member.email})
    assert disabled.status_code == 200
    assert disabled.json()["user"]["is_active"] is False
    assert client.get("/api/v1/users/me", headers=auth(member_token)).status_code in (401, 403)
    assert db_session.get(User, member.id).auth_epoch == 1

    enabled = client.patch(path, headers=auth(token),
                           json={"action": "enable", "confirm_email": member.email})
    assert enabled.status_code == 200
    assert enabled.json()["user"]["is_active"] is True
    assert db_session.get(User, member.id).auth_epoch == 2
    # An old access or refresh ticket must never regain validity.
    assert client.get("/api/v1/users/me", headers=auth(member_token)).status_code == 401


def test_admin_self_and_other_admin_are_immutable(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    first, token = add_user(db_session, "first-owner@example.com")
    second, _ = add_user(db_session, "aqlyra.verify@gmail.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", first.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", second.email)
    for protected in (first, second):
        path = f"/api/v1/admin/users/{protected.id}/status"
        response = client.patch(
            path, headers=auth(token),
            json={"action": "disable", "confirm_email": protected.email},
        )
        assert response.status_code == 403
    assert first.is_active and second.is_active


def test_delete_locked_without_explicit_backend_feature_gate(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    admin, token = add_user(db_session, "operator-delete@example.com")
    target, _ = add_user(db_session, "target-delete@example.com")
    target.is_active = False
    db_session.commit()
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "")
    monkeypatch.setattr(settings, "ADMIN_ACCOUNT_DELETION_ENABLED", False)
    response = client.request(
        "DELETE", f"/api/v1/admin/users/{target.id}",
        headers=auth(token),
        json={"confirm_email": target.email, "confirmation": "DELETE ACCOUNT"},
    )
    assert response.status_code == 403
    assert db_session.get(User, target.id) is not None


def test_delete_only_disabled_empty_account_with_full_confirmation(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    admin, token = add_user(db_session, "delete-owner@example.com")
    target, _ = add_user(db_session, "empty-target@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "")
    monkeypatch.setattr(settings, "ADMIN_ACCOUNT_DELETION_ENABLED", True)
    endpoint = f"/api/v1/admin/users/{target.id}"
    details = {"confirm_email": target.email, "confirmation": "DELETE ACCOUNT"}

    assert client.request("DELETE", endpoint, headers=auth(token),
                          json=details).status_code == 409  # still enabled
    target.is_active = False
    db_session.commit()
    assert client.request("DELETE", endpoint, headers=auth(token),
                          json={"confirm_email": target.email,
                                "confirmation": "DELETE"}).status_code == 422
    assert client.request("DELETE", endpoint, headers=auth(token),
                          json={"confirm_email": "mismatch@example.com",
                                "confirmation": "DELETE ACCOUNT"}).status_code == 409
    deleted = client.request("DELETE", endpoint, headers=auth(token), json=details)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert db_session.get(User, target.id) is None


def test_delete_rejects_accounts_with_uploaded_files(
    client: TestClient, db_session: Session, monkeypatch,
) -> None:
    admin, token = add_user(db_session, "files-owner@example.com")
    target, _ = add_user(db_session, "has-files@example.com")
    target.is_active = False
    db_session.add(Document(
        user_id=target.id,
        original_filename="private.pdf",
        stored_filename="private.pdf",
        storage_path="/test/private.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=100,
        checksum_sha256="0" * 64,
    ))
    db_session.commit()
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin.id)
    monkeypatch.setattr(settings, "ADMIN_OWNER_EMAIL", "")
    monkeypatch.setattr(settings, "ADMIN_ACCOUNT_DELETION_ENABLED", True)
    response = client.request(
        "DELETE", f"/api/v1/admin/users/{target.id}",
        headers=auth(token),
        json={"confirm_email": target.email, "confirmation": "DELETE ACCOUNT"},
    )
    assert response.status_code == 409
    assert db_session.get(User, target.id) is not None


@pytest.mark.parametrize("value", [
    "admin", "admin@localhost", "not an email", "admin@example.com,other@example.com",
])
def test_invalid_owner_email_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, ADMIN_OWNER_EMAIL=value)
