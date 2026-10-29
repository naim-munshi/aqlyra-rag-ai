"""Regression tests for main-chat web intent, privacy and citations."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import auto_web_research_service as planner
from app.services import chat_service


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What are the latest AI research developments this month?", "search"),
        ("I want the latest verified AI news", "search"),
        ("Compare the latest GPU inference prices", "compare"),
        ("Fact-check whether today's headline is correct", "fact_check"),
        ("Do a deep research on current AI agents", "deep"),
        ("আজকের AI খবর কী?", "search"),
        ("最新のAIニュースを教えて", "search"),
        ("Explain binary search algorithm", None),
        ("Write a poem about today", None),
        ("Please summarize my uploaded document today", None),
        ("What are the latest jobs? Do not use web.", None),
        ("Don't use the web. What is current today?", None),
        ("What happened to my account today?", None),
        ("What are the latest updates about my uploaded private document?", None),
    ],
)
def test_auto_web_intent(monkeypatch, question, expected):
    monkeypatch.setattr(planner.settings, "WEB_RESEARCH_ENABLED", True)
    assert planner.choose_web_mode(question, "auto") == expected


def test_explicit_control_respects_fail_closed_configuration(monkeypatch):
    monkeypatch.setattr(planner.settings, "WEB_RESEARCH_ENABLED", False)
    assert planner.choose_web_mode("latest news?", "auto") is None
    assert planner.choose_web_mode("latest news?", "off") is None
    # A forced selection must reach the provider and report 503 if unconfigured,
    # never silently pretend that an LLM-only reply was web-researched.
    assert planner.choose_web_mode("Explain networking", "on") == "search"
    assert planner.choose_web_mode("Explain networking", "deep") == "deep"


def test_web_query_does_not_read_history_or_personal_memory(monkeypatch):
    monkeypatch.setattr(planner.settings, "WEB_RESEARCH_ENABLED", True)
    calls = []
    def mock_research(question, *, max_sources, mode, time_range, provider, iterative):
        calls.append((question, max_sources, mode, time_range, iterative))
        return SimpleNamespace(
            answer="The public result is verified [W1].",
            sources=[SimpleNamespace(
                citation="[W1]", title="Source [untrusted](markdown)",
                url="https://example.org/report"
            )],
            provider_name="mock-web-llm", model_name="mock-model",
        )
    monkeypatch.setattr(chat_service, "research_web", mock_research)
    monkeypatch.setattr(chat_service, "get_recent_messages_for_conversation",
                        lambda **kwargs: pytest.fail("Read private chat history"))
    monkeypatch.setattr(chat_service, "_retrieve_normal_chat_memories",
                        lambda **kwargs: pytest.fail("Read private memory"))
    private_conversation = SimpleNamespace(mode="normal", user_id="private-user", id="private-chat")
    result = chat_service.execute_chat_turn(
        db=Mock(), conversation=private_conversation,
        message="What are the latest AI developments?", web_mode="auto",
    )
    assert calls == [("What are the latest AI developments?", 5, "search", "month", False)]
    assert "[W1]" in result.content
    assert "[Source  untrusted  markdown](https://example.org/report)" in result.content
    assert "[S1]" not in result.content
    assert result.citations == ()
    assert result.mode == "normal"


def test_knowledge_never_calls_public_web(monkeypatch):
    monkeypatch.setattr(chat_service, "research_web",
                        lambda *args, **kwargs: pytest.fail("Public web called"))
    monkeypatch.setattr(chat_service, "generate_knowledge_chat_reply",
                        lambda **kwargs: "knowledge-only")
    response = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(mode="knowledge"),
        message="Latest private document changes?", web_mode="deep",
    )
    assert response == "knowledge-only"


def test_attachment_never_calls_public_web(monkeypatch):
    monkeypatch.setattr(chat_service, "research_web",
                        lambda *args, **kwargs: pytest.fail("Public web called"))
    monkeypatch.setattr(chat_service, "generate_normal_document_chat_reply",
                        lambda **kwargs: "attachment-only")
    response = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(mode="normal"),
        message="Latest findings in this private file?",
        document_ids=("owned-file-id",), web_mode="on",
    )
    assert response == "attachment-only"


def test_web_mode_schema_rejects_untrusted_values():
    from pydantic import ValidationError
    from app.schemas.conversation import ConversationMessageCreate
    assert ConversationMessageCreate(content="hello").web_mode == "auto"
    assert ConversationMessageCreate(content="hello", web_mode="off").web_mode == "off"
    with pytest.raises(ValidationError):
        ConversationMessageCreate(content="hello", web_mode="arbitrary_url")

@pytest.mark.parametrize("question,window", [
    ("Find today's AI news", "day"),
    ("What happened this week?", "week"),
    ("Review this month news", "month"),
    ("This year's market changes", "year"),
    ("Latest scientific discoveries", "month"),
    ("Explain Python closures", None),
    ("Explain the 2028 admission process", None),
])
def test_freshness_window(question, window):
    assert planner.detect_time_range(question) == window


def test_overlong_explicit_web_message_fails_before_external_provider(monkeypatch):
    monkeypatch.setattr(chat_service, "research_web",
                        lambda *args, **kwargs: pytest.fail("Oversized prompt leaked to provider"))
    question = "latest news " + ("x" * 610)
    with pytest.raises(chat_service.ChatValidationError, match="600 characters"):
        chat_service.execute_chat_turn(
            db=Mock(), conversation=SimpleNamespace(mode="normal"),
            message=question, web_mode="on",
        )


def test_authenticated_auto_web_chat_persists_cited_reply(client, monkeypatch):
    """Real authenticated conversation API: web response is saved and readable."""
    from app.schemas.web_research import WebResearchSource

    monkeypatch.setattr(planner.settings, "WEB_RESEARCH_ENABLED", True)
    searched = []
    def mock_research(question, **options):
        searched.append((question, options["mode"], options["time_range"]))
        return SimpleNamespace(
            answer="The verified finding [W1].",
            sources=[WebResearchSource(
                citation="[W1]", title="Official evidence",
                url="https://example.org/official", excerpt="Evidence",
                published_date=None,
            )],
            provider_name="mock-live", model_name="mock-source",
        )
    monkeypatch.setattr(chat_service, "research_web", mock_research)
    registered = client.post("/api/v1/auth/register", json={
        "username": "auto_web_user",
        "email": "auto_web_user@example.com",
        "password": "StrongPassword321!",
    })
    assert registered.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "email": "auto_web_user@example.com",
        "password": "StrongPassword321!",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    create = client.post("/api/v1/conversations", json={
        "title": "AI news", "mode": "normal",
    }, headers=headers)
    assert create.status_code == 201
    conv_id = create.json()["id"]
    question = "What is the latest AI news this week?"
    response = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": question, "web_mode": "auto"}, headers=headers,
    )
    assert response.status_code == 200, response.text[:500]
    answer = response.json()["assistant_message"]
    assert answer["content"].startswith("The verified finding [W1].")
    assert "https://example.org/official" in answer["content"]
    assert searched == [(question, "search", "week")]
    restored = client.get(
        f"/api/v1/conversations/{conv_id}/messages", headers=headers,
    )
    assert restored.status_code == 200
    assert any("https://example.org/official" in m["content"]
               for m in restored.json() if m["role"] == "assistant")


def test_authenticated_streamed_forced_web_keeps_sse_contract(client, monkeypatch):
    monkeypatch.setattr(planner.settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(chat_service, "research_web", lambda question, **kwargs: SimpleNamespace(
        answer="Sourced [W1].",
        sources=[SimpleNamespace(citation="[W1]", title="Official",
                                 url="https://example.org/source")],
        provider_name="stub", model_name="stub",
    ))
    client.post("/api/v1/auth/register", json={
        "username": "auto_web_stream_user",
        "email": "auto_web_stream_user@example.com",
        "password": "StrongPassword321!",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "auto_web_stream_user@example.com",
        "password": "StrongPassword321!",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    create = client.post("/api/v1/conversations", json={
        "title": "Web SSE", "mode": "normal",
    }, headers=headers)
    assert create.status_code == 201
    conv_id = create.json()["id"]
    result = client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Find official evidence", "web_mode": "on"},
        headers=headers,
    )
    assert result.status_code == 200
    assert "event: start" in result.text
    assert "event: delta" in result.text
    assert "event: complete" in result.text
    assert "https://example.org/source" in result.text
