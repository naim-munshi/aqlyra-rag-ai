"""Owner-only operational metrics: tenant isolation and safe aggregate responses."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings, settings
from app.core.monitoring import admin_http_snapshot, reset_metrics_for_tests
from app.models.user import User


def _new_user(client: TestClient, label: str) -> tuple[str, str]:
    data = {
        "username": "admin_" + label + uuid4().hex[:8],
        "email": label + uuid4().hex[:8] + "@example.com",
        "password": "TestPassword012!",
    }
    assert client.post("/api/v1/auth/register", json=data).status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": data["email"], "password": data["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer " + token}
    ).json()
    return me["id"], token


def test_admin_is_disabled_by_default(client: TestClient, monkeypatch) -> None:
    uid, token = _new_user(client, "disabled")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    assert client.get("/api/v1/admin/overview").status_code == 401
    result = client.get(
        "/api/v1/admin/overview", headers={"Authorization": "Bearer " + token}
    )
    assert result.status_code == 403
    assert uid not in result.text


def test_owner_can_read_only_aggregates(
    client: TestClient, monkeypatch,
) -> None:
    admin_id, admin_token = _new_user(client, "owner")
    user_id, user_token = _new_user(client, "other")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    forbidden = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + user_token},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store, private"
    body = allowed.json()
    assert body["users"]["registered_total"] == 2
    assert body["users"]["active_accounts"] == 2
    assert len(body["users"]["signups_last_7_days"]) == 7
    assert sum(day["count"] for day in body["users"]["signups_last_7_days"]) == 2
    assert body["traffic"]["scope"] == "single_backend_process"
    assert body["cloud_storage"]["scope"] == "database_aggregate"
    for metric in ("claimed", "stale_claimed", "cleanup_candidates", "failed_intents"):
        assert body["cloud_storage"][metric] == 0
    assert "request_total" in body["traffic"]
    serialized = allowed.text
    for private in (admin_id, user_id, admin_token, user_token, "@example.com"):
        assert private not in serialized
    assert "username" not in serialized
    assert "ip_address" not in serialized
    assert "access_token" not in serialized


def test_unverified_allowlisted_user_cannot_read(
    client: TestClient, db_session, monkeypatch,
) -> None:
    user_id, token = _new_user(client, "pending")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    user = db_session.get(User, user_id)
    assert user is not None
    user.email_verified_at = None
    db_session.flush()
    assert client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + token},
    ).status_code == 403


def test_monitoring_does_not_include_raw_user_paths() -> None:
    reset_metrics_for_tests()
    snap = admin_http_snapshot()
    assert snap["request_total"] == 0
    assert snap["routes"] == []


@pytest.mark.parametrize("value", [
    "user@example.com", "admin", "123", "f" * 120,
    "9d4c4bc2-a367-485d-b332-60a73d894e9b,admin",
])
def test_invalid_admin_ids_rejected(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, ADMIN_USER_IDS=value)



def test_prometheus_metrics_are_private_to_verified_admin(
    client: TestClient, db_session, monkeypatch,
) -> None:
    """The backend /metrics route must never expose traffic to strangers."""
    reset_metrics_for_tests()
    admin_id, admin_token = _new_user(client, "metricsowner")
    ordinary_id, ordinary_token = _new_user(client, "metricsother")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    anonymous = client.get("/api/v1/metrics")
    assert anonymous.status_code == 401
    assert "aqlyra_http_requests_total" not in anonymous.text

    denied = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer " + ordinary_token},
    )
    assert denied.status_code == 403
    assert "aqlyra_http_requests_total" not in denied.text

    allowed = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert allowed.status_code == 200
    assert "aqlyra_http_requests_total" in allowed.text
    assert allowed.headers["cache-control"] == "private, no-store"
    assert "text/plain" in allowed.headers["content-type"]

    admin = db_session.get(User, admin_id)
    assert admin is not None
    admin.email_verified_at = None
    db_session.flush()
    revoked = client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert revoked.status_code == 403
    assert "aqlyra_http_requests_total" not in revoked.text
    assert ordinary_id not in revoked.text


def test_admin_chat_activity_is_distinct_and_privacy_preserving(
    client: TestClient, db_session, monkeypatch,
) -> None:
    from datetime import timedelta

    from app.core.datetime_utils import utc_now_naive
    from app.models.conversation import Conversation
    from app.models.message import Message

    admin_id, admin_token = _new_user(client, "activityowner")
    other_id, other_token = _new_user(client, "activityother")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    owner_chat = Conversation(user_id=admin_id, mode="normal", title="Private owner")
    other_chat = Conversation(user_id=other_id, mode="normal", title="Private other")
    old_chat = Conversation(user_id=other_id, mode="normal", title="Older private")
    db_session.add_all([owner_chat, other_chat, old_chat])
    db_session.flush()

    now = utc_now_naive()
    db_session.add_all([
        Message(conversation_id=owner_chat.id, role="user", mode="normal",
                content="very private chat content A", created_at=now - timedelta(minutes=10)),
        Message(conversation_id=owner_chat.id, role="user", mode="normal",
                content="very private chat content B", created_at=now - timedelta(minutes=5)),
        Message(conversation_id=owner_chat.id, role="assistant", mode="normal",
                content="private assistant response", created_at=now - timedelta(minutes=4)),
        Message(conversation_id=other_chat.id, role="user", mode="normal",
                content="very private chat content C", created_at=now - timedelta(days=2)),
        Message(conversation_id=old_chat.id, role="user", mode="normal",
                content="very old private chat", created_at=now - timedelta(days=9)),
    ])
    db_session.flush()

    forbidden = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + other_token},
    )
    assert forbidden.status_code == 403

    response = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert response.status_code == 200
    activity = response.json()["chat_activity"]
    assert activity["scope"] == "persisted_authenticated_user_messages"
    assert activity["active_users_last_24h"] == 1
    assert activity["active_users_last_7d"] == 2
    assert activity["user_messages_last_24h"] == 2
    assert activity["user_messages_last_7d"] == 3
    assert len(activity["daily_last_7_utc_days"]) == 7
    assert sum(row["messages"] for row in activity["daily_last_7_utc_days"]) == 3
    assert all(row["users"] <= row["messages"] for row in activity["daily_last_7_utc_days"])
    for forbidden_data in (
        admin_id, other_id, "very private chat content", "private assistant",
        "Private owner", "Private other",
    ):
        assert forbidden_data not in response.text


def test_admin_chat_activity_zero_for_new_accounts(
    client: TestClient, monkeypatch,
) -> None:
    admin_id, token = _new_user(client, "emptyactivity")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    response = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 200
    activity = response.json()["chat_activity"]
    assert activity["active_users_last_24h"] == 0
    assert activity["active_users_last_7d"] == 0
    assert activity["user_messages_last_24h"] == 0
    assert activity["user_messages_last_7d"] == 0
    assert all(day["users"] == 0 and day["messages"] == 0
               for day in activity["daily_last_7_utc_days"])


def test_admin_rag_coverage_counts_only_matching_current_vectors(
    client: TestClient, db_session, monkeypatch,
) -> None:
    """Report must not count stale hashes or leak other tenants' filenames."""
    from hashlib import sha256
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.embedding_record import EmbeddingRecord
    from app.embeddings.remote_semantic_provider import MODEL

    admin_id, admin_token = _new_user(client, "ragcoveradmin")
    user_id, user_token = _new_user(client, "ragcoverother")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    for owner_id, suffix, texts in (
        (admin_id, "one", ("Current vector", "Stale vector")),
        (user_id, "two", ("Missing vector",)),
    ):
        document = Document(
            user_id=owner_id, original_filename="secret_" + suffix + ".md",
            stored_filename="private_" + suffix + ".md",
            storage_path="cloud://documents/test/" + uuid4().hex + ".md",
            file_extension=".md", content_type="text/markdown",
            file_size=10, checksum_sha256="a" * 64, status="ready",
        )
        db_session.add(document)
        db_session.flush()
        for idx, body in enumerate(texts):
            chunk = DocumentChunk(
                document_id=document.id, chunk_index=idx,
                source_label="private " + suffix, content=body,
                embedding_content=body, content_hash=sha256(body.encode()).hexdigest(),
                token_count=3, char_count=len(body), word_count=2,
            )
            db_session.add(chunk)
            db_session.flush()
            if body != "Missing vector":
                db_session.add(EmbeddingRecord(
                    chunk_id=chunk.id, provider_name="remote_onnx",
                    model_name=MODEL, dimension=384,
                    content_hash=("f" * 64 if body == "Stale vector" else chunk.content_hash),
                    embedding=[0.0] * 383 + [1.0], input_token_count=3,
                ))
    db_session.flush()
    route = "/api/v1/admin/rag-coverage"
    assert client.get(route).status_code == 401
    assert client.get(route, headers={"Authorization": "Bearer " + user_token}).status_code == 403
    response = client.get(route, headers={"Authorization": "Bearer " + admin_token})
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["vary"] == "Cookie"
    values = response.json()["semantic_index"]
    assert values["ready_documents"] == 2
    assert values["eligible_chunks"] == 3
    assert values["indexed_chunks"] == 1
    assert values["missing_or_stale_chunks"] == 2
    assert values["coverage_percent"] == 33.33
    for private in (admin_id, user_id, "secret_one", "secret_two", "@example.com"):
        assert private not in response.text


def test_admin_rag_coverage_reports_empty_index_safely(
    client: TestClient, monkeypatch,
) -> None:
    admin_id, token = _new_user(client, "ragcoverempty")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    response = client.get("/api/v1/admin/rag-coverage", headers={
        "Authorization": "Bearer " + token,
    })
    assert response.status_code == 200
    assert response.json()["semantic_index"]["eligible_chunks"] == 0
    assert response.json()["semantic_index"]["coverage_percent"] == 100.0
