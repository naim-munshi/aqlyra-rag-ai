"""Bounded, synthetic, actual FastAPI chat-concurrency regression.

This exercises real authenticated request routing, DB sessions, chat persistence
and a deterministic CI LLM. It is NOT a production/Groq capacity benchmark.
"""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.main import app


PASSWORD = "SyntheticChatTest123!"


def _make_synthetic_employee(client: TestClient, index: int):
    identity = f"multiuser-employee-{index:02d}"
    email = f"{identity}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "username": identity,
            "email": email,
            "password": PASSWORD,
        },
    )
    assert registered.status_code == 201, registered.text
    logged = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert logged.status_code == 200, logged.text
    headers = {"Authorization": f"Bearer {logged.json()['access_token']}"}
    created = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Concurrent user QA", "mode": "normal"},
    )
    assert created.status_code == 201, created.text
    return headers, created.json()["id"], f"Hello from QA employee {index:02d}"


def test_25_independent_authenticated_chat_turns_concurrent(
    client: TestClient, db_session: Session,
) -> None:
    # Register serially with the standard test fixture; isolate DB sessions
    # per concurrent request, just as the deployed FastAPI dependency does.
    accounts = [_make_synthetic_employee(client, i) for i in range(25)]
    original_override = app.dependency_overrides.get(get_db)
    engine = db_session.get_bind()

    def independent_db():
        db = Session(bind=engine)
        try:
            yield db
        finally:
            db.close()

    def send_one(account):
        headers, conversation_id, question = account
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": question},
        )
        return response.status_code, response.json(), question

    try:
        app.dependency_overrides[get_db] = independent_db
        # 25 distinct account requests, at most 10 simultaneous workers.
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(send_one, accounts))
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original_override

    assert len(results) == 25
    for status, payload, question in results:
        assert status == 200, payload
        assert payload["mode"] == "normal"
        assert payload["user_message"]["content"] == question
        assert payload["user_message"]["role"] == "user"
        assert payload["assistant_message"]["role"] == "assistant"

    # Each user sees only its own persisted turn after the concurrency burst.
    for headers, conversation_id, question in accounts:
        history = client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=headers,
        )
        assert history.status_code == 200, history.text
        items = history.json()
        assert len(items) == 2
        assert items[0]["role"] == "user"
        assert items[0]["content"] == question
        assert items[1]["role"] == "assistant"
        assert "Hello from QA employee" not in items[1]["content"]
