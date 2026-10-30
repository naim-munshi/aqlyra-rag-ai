"""Single-pass AI public tool selection regression; no paid provider/network."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import chat_service, smart_web_router as router
from app.services import auto_web_research_service as web_rules


class StubSelector:
    def __init__(self, result='{"search":true,"mode":"search"}', *, throws=False):
        self.result = result
        self.throws = throws
        self.calls = []

    def generate(self, *, instructions, input_text):
        self.calls.append((instructions, json.loads(input_text)))
        if self.throws:
            raise RuntimeError("selector unavailable")
        return SimpleNamespace(text=self.result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(web_rules.settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(web_rules.settings, "TAVILY_API_KEY", "test-only-key")


def test_ambiguous_public_job_lookup_calls_ai_once(enabled):
    model = StubSelector()
    query = "Find AI engineer jobs in Tokyo"
    assert router.route_web_request(query, provider=model) == "search"
    assert len(model.calls) == 1
    assert model.calls[0][1] == {"public_question": query}
    assert "PRIVATE" not in model.calls[0][1]


def test_automatic_deep_intent_preserves_user_overrides(enabled):
    model = StubSelector('{"search":true,"mode":"compare"}')
    assert router.route_web_request("Compare salary ranges for AI roles in Japan", provider=model) == "compare"
    assert router.route_web_request("Find scholarships in Japan", "off", provider=model) is None
    assert router.route_web_request("Explain CPU registers", "on", provider=model) == "search"
    assert router.route_web_request("Find AI jobs", "deep", provider=model) == "deep"
    assert len(model.calls) == 1


@pytest.mark.parametrize("question", [
    "Can you find my salary details today?",
    "What are the latest updates in my uploaded file?",
    "What was my password and OTP today?",
    "Show my refresh token now",
    "What is the price of a bank account with my private details?",
    "What are today's prices? Do not use web.",
])
def test_private_and_no_web_never_call_selector(enabled, question):
    model = StubSelector()
    assert router.route_web_request(question, provider=model) is None
    assert model.calls == []


@pytest.mark.parametrize("question", [
    "Write a story about hotels.",
    "Explain how Python dictionaries work.",
    "My job application is failing.",
    "Give me the best advice for my scholarship essay.",
])
def test_non_public_question_never_calls_selector(enabled, question):
    model = StubSelector()
    assert router.route_web_request(question, provider=model) is None
    assert not model.calls


@pytest.mark.parametrize("response", [
    '{"search":true,"mode":"wrong"}',
    '{"search":"yes","mode":"search"}',
    '{"search":true,"mode":"search","url":"https://evil.test"}',
    "sure I searched",
    '[]',
    '{"search":false,"mode":"search"}',
])
def test_model_responses_fail_closed(enabled, response):
    model = StubSelector(response)
    assert router.route_web_request("Find AI engineer jobs in Tokyo", provider=model) is None
    assert len(model.calls) == 1


def test_model_exception_falls_back_to_normal_chat(enabled):
    assert router.route_web_request("Find AI engineer jobs in Tokyo", provider=StubSelector(throws=True)) is None


def test_disabled_web_never_calls_ai_selector(monkeypatch):
    monkeypatch.setattr(web_rules.settings, "WEB_RESEARCH_ENABLED", False)
    model = StubSelector()
    assert router.route_web_request("Find AI engineer jobs in Tokyo", provider=model) is None
    assert model.calls == []


def test_normal_sync_chat_routes_public_question_through_verified_research(enabled, monkeypatch):
    query = "Find AI engineer jobs in Tokyo"
    selector = StubSelector('{"search":true,"mode":"search"}')
    invoked = []
    def fake_web(question, **kwargs):
        invoked.append((question, kwargs["mode"], kwargs["max_sources"]))
        return SimpleNamespace(
            answer="Only cited evidence [W1].",
            sources=[SimpleNamespace(citation="[W1]",title="A public source",url="https://example.org/jobs")],
            provider_name="mock",model_name="mock",
        )
    monkeypatch.setattr(chat_service, "research_web", fake_web)
    result = chat_service.execute_chat_turn(
        db=Mock(),conversation=SimpleNamespace(mode="normal",id="conversation",user_id="owner"),
        message=query, web_mode="auto",provider=selector,
    )
    assert invoked == [(query,"search",5)]
    assert len(selector.calls) == 1
    assert "https://example.org/jobs" in result.content
    assert "[W1]" in result.content


def test_routed_decision_does_not_rerun_model(enabled, monkeypatch):
    query = "Find AI engineer jobs in Tokyo"
    monkeypatch.setattr(chat_service,"route_web_request",
                        lambda *args,**kwargs: pytest.fail("Reclassified stream request"))
    monkeypatch.setattr(chat_service,"research_web",lambda question,**kwargs: SimpleNamespace(
        answer="Result [W1].",
        sources=[SimpleNamespace(citation="[W1]",title="Source",url="https://example.org/result")],
        provider_name="mock",model_name="mock",
    ))
    result = chat_service.execute_chat_turn(
        db=Mock(),conversation=SimpleNamespace(mode="normal",id="conversation",user_id="owner"),
        message=query,web_mode="auto",routed_web_mode="search",
    )
    assert "https://example.org/result" in result.content



def test_authenticated_stream_auto_ai_selects_web_once(client, enabled, monkeypatch):
    """Actual chat SSE responds with tool status, citation, and one AI choice."""
    model = StubSelector()
    monkeypatch.setattr(router.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(router, "create_configured_llm_provider", lambda: model)
    calls = []
    monkeypatch.setattr(chat_service, "research_web", lambda question, **kwargs: (
        calls.append((question, kwargs["mode"])) or SimpleNamespace(
            answer="Two public roles [W1].",
            sources=[SimpleNamespace(citation="[W1]", title="Public job board",
                                     url="https://example.org/jobs")],
            provider_name="stub", model_name="stub",
        )
    ))
    registered = client.post("/api/v1/auth/register", json={
        "username": "ai_search_stream_user",
        "email": "ai_search_stream_user@example.com",
        "password": "StrongPassword321!",
    })
    assert registered.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "email": "ai_search_stream_user@example.com",
        "password": "StrongPassword321!",
    })
    assert login.status_code == 200
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post("/api/v1/conversations", json={
        "title": "Auto web integration", "mode": "normal",
    }, headers=auth)
    assert created.status_code == 201
    identifier = created.json()["id"]
    question = "Find AI engineer jobs in Tokyo"
    answer = client.post(
        f"/api/v1/conversations/{identifier}/messages/stream",
        json={"content": question, "web_mode": "auto"}, headers=auth,
    )
    assert answer.status_code == 200
    assert "event: tool_status" in answer.text
    assert '"status":"searching"' in answer.text
    assert "event: complete" in answer.text
    assert "https://example.org/jobs" in answer.text
    assert calls == [(question, "search")]
    assert len(model.calls) == 1


def test_auto_chat_without_tavily_key_avoids_live_search_errors(monkeypatch):
    monkeypatch.setattr(web_rules.settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(web_rules.settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(web_rules.settings, "TAVILY_KEYLESS_ENABLED", False)
    model = StubSelector()
    assert router.route_web_request("What's the latest news today?", provider=model) is None
    assert model.calls == []
    # Explicitly selected web mode never falsely claims online citations.
    assert router.route_web_request("Find AI jobs", mode="on", provider=model) == "search"
