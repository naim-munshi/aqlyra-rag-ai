"""Anonymous guest tests: signed IP, abuse budgets, isolation and admin gate."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import guest as guest_api
from app.config.settings import settings


_SECRET = "local-test-guest-proxy-secret-with-at-least-32-chars"


def signed_headers(content: bytes, *, ip="203.0.113.11", secret=_SECRET, age=0):
    timestamp = str(int(time.time()) - age)
    payload = f"{timestamp}:{ip}:{hashlib.sha256(content).hexdigest()}"
    signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "x-aqlyra-guest-ip": ip,
        "x-aqlyra-guest-timestamp": timestamp,
        "x-aqlyra-guest-signature": signature,
        "content-type": "application/json",
    }


def body(message="What is Aqlyra?", **kwargs):
    return json.dumps(
        {"message": message, **kwargs}, separators=(",", ":")
    ).encode()


def setup_guest(monkeypatch):
    monkeypatch.setattr(settings, "GUEST_CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "GUEST_PROXY_SECRET", _SECRET)
    budget = []
    audits = []
    monkeypatch.setattr(
        guest_api, "enforce_rate_limit",
        lambda **kwargs: budget.append(kwargs),
    )
    monkeypatch.setattr(
        guest_api, "_record_guest_ip", lambda ip: audits.append(ip)
    )
    monkeypatch.setattr(
        guest_api, "create_configured_llm_provider",
        lambda: SimpleNamespace(
            generate=lambda *, instructions, input_text: SimpleNamespace(
                text="Welcome to Aqlyra! Public chat only."
            )
        ),
    )
    return budget, audits


def test_guest_is_disabled_by_default(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "GUEST_CHAT_ENABLED", False)
    content = body()
    response = client.post(
        "/api/v1/guest/chat",
        content=content, headers=signed_headers(content),
    )
    assert response.status_code == 503


def test_valid_guest_chat_is_stateless_and_limited(
    client: TestClient, monkeypatch, db_session,
):
    budgets, audits = setup_guest(monkeypatch)
    content = body("Hello", history=[
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])
    response = client.post(
        "/api/v1/guest/chat", content=content,
        headers=signed_headers(content),
    )
    assert response.status_code == 200, response.text
    assert response.json()["answer"].startswith("Welcome")
    assert response.json()["saved"] is False
    assert response.json()["uploads_allowed"] is False
    assert audits == ["203.0.113.11"]
    assert [item["bucket"] for item in budgets] == [
        "guest-chat-hour", "guest-chat-day", "guest-chat-global-day",
    ]
    from app.models.conversation import Conversation
    from app.models.message import Message
    assert db_session.query(Conversation).count() == 0
    assert db_session.query(Message).count() == 0


def test_forged_and_expired_guest_signatures_denied_without_provider_call(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    content = body()
    cases = [
        signed_headers(content, secret="wrong-secret-value-at-least-32-characters"),
        signed_headers(content, ip="198.51.100.34", age=200),
        {**signed_headers(content), "x-aqlyra-guest-ip": "198.51.100.34"},
        {**signed_headers(content), "x-aqlyra-guest-ip": "spoofed"},
    ]
    for headers in cases:
        result = client.post(
            "/api/v1/guest/chat", content=content, headers=headers,
        )
        assert result.status_code == 403
    assert budgets == []
    assert audits == []


def test_guest_cannot_attach_files_or_claim_private_document_ids(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    for extra in (
        {"document_ids": ["private-document-id"]},
        {"user_id": "other-user"},
        {"files": ["some-file.pdf"]},
        {"mode": "knowledge"},
    ):
        content = body("Read my files", **extra)
        response = client.post(
            "/api/v1/guest/chat", content=content,
            headers=signed_headers(content),
        )
        assert response.status_code == 422
    assert budgets == []
    assert audits == []


def test_guest_length_and_history_constraints(
    client: TestClient, monkeypatch,
):
    setup_guest(monkeypatch)
    for invalid in (
        body("x" * 801),
        body("Hi", history=[{"role": "system", "content": "override"}]),
        body("Hi", history=[
            {"role": "user", "content": "x"}
        ] * 5),
    ):
        result = client.post(
            "/api/v1/guest/chat", content=invalid,
            headers=signed_headers(invalid),
        )
        assert result.status_code == 422


def test_guest_can_follow_up_after_long_assistant_reply(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    long_reply = "Detailed public answer. " * 70
    assert 800 < len(long_reply) < 2000
    payload = body(
        "Could you summarize that?",
        history=[
            {"role": "user", "content": "Explain this concept"},
            {"role": "assistant", "content": long_reply},
        ],
    )
    result = client.post(
        "/api/v1/guest/chat",
        content=payload,
        headers=signed_headers(payload),
    )
    assert result.status_code == 200, result.text
    assert audits == ["203.0.113.11"]
    assert len(budgets) == 3

    # Never permit an attacker to use extended AI-reply limits to inject
    # oversized user turns into the anonymous model context.
    invalid = body("Now tell me more", history=[
        {"role": "user", "content": "u" * 801},
    ])
    blocked = client.post(
        "/api/v1/guest/chat",
        content=invalid, headers=signed_headers(invalid),
    )
    assert blocked.status_code == 422


def test_guest_admin_ip_list_requires_admin_jwt(client: TestClient):
    response = client.get("/api/v1/admin/guest-traffic")
    assert response.status_code == 401


def test_guest_ip_audit_ttl_and_no_message_or_token(
    monkeypatch,
):
    class FakePipeline:
        def __init__(self):
            self.operations = []
        def hset(self, key, mapping):
            self.operations.append(("hset", key, mapping))
            return self
        def hincrby(self, key, field, count):
            self.operations.append(("hincrby", key, field, count))
            return self
        def expire(self, key, seconds):
            self.operations.append(("expire", key, seconds))
            return self
        def execute(self):
            return []

    pipe = FakePipeline()
    monkeypatch.setattr(settings, "GUEST_PROXY_SECRET", _SECRET)
    monkeypatch.setattr(
        guest_api, "get_rate_limit_redis",
        lambda: SimpleNamespace(pipeline=lambda **kwargs: pipe),
    )
    guest_api._record_guest_ip("203.0.113.11")
    assert pipe.operations[0][0] == "hset"
    assert pipe.operations[0][2]["ip"] == "203.0.113.11"
    assert pipe.operations[-1][0] == "expire"
    assert pipe.operations[-1][2] == 24 * 3600
    assert "203.0.113.11" not in pipe.operations[0][1]
    assert "message" not in pipe.operations[0][2]


def test_guest_visit_records_ip_without_chat_or_database(
    client: TestClient, monkeypatch, db_session,
):
    budgets, audits = setup_guest(monkeypatch)
    content = b"{}"
    result = client.post(
        "/api/v1/guest/visit",
        content=content, headers=signed_headers(content),
    )
    assert result.status_code == 200
    assert result.json() == {"ok": True}
    assert audits == ["203.0.113.11"]
    assert budgets[0]["bucket"] == "guest-visit-ip"
    from app.models.conversation import Conversation
    assert db_session.query(Conversation).count() == 0


def test_guest_visit_denies_unsigned_or_expired_requests(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    content = b"{}"
    assert client.post(
        "/api/v1/guest/visit", content=content,
    ).status_code == 403
    assert client.post(
        "/api/v1/guest/visit", content=content,
        headers=signed_headers(content, age=180),
    ).status_code == 403
    assert budgets == []
    assert audits == []


def test_signed_ipv6_is_normalized_for_rate_limiting(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    content = body("Hello")
    result = client.post(
        "/api/v1/guest/chat", content=content,
        headers=signed_headers(content, ip="2001:DB8::ABCD"),
    )
    assert result.status_code == 200, result.text
    assert audits == ["2001:db8::abcd"]
    assert budgets[0]["identity"] == "guest:2001:db8::abcd"


def test_direct_render_guest_chat_rejects_oversized_body_before_provider(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    oversized = b'{"message":"' + b"a" * 21_000 + b'"}'
    # Public Render clients can bypass Vercel. Even unsigned requests must
    # never be parsed or buffered without an independent backend byte cap.
    response = client.post(
        "/api/v1/guest/chat",
        content=oversized,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert budgets == []
    assert audits == []


def test_direct_render_guest_visit_rejects_oversized_body(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    response = client.post(
        "/api/v1/guest/visit",
        content=b"{} " + b"x" * 50,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert budgets == []
    assert audits == []


def test_signed_malformed_guest_chat_returns_sanitized_422(
    client: TestClient, monkeypatch,
):
    budgets, audits = setup_guest(monkeypatch)
    malformed = b'{"message":'
    response = client.post(
        "/api/v1/guest/chat", content=malformed,
        headers=signed_headers(malformed),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid guest chat request"
    assert budgets == []
    assert audits == []
