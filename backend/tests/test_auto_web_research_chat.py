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
        ("Compare the latest GPU inference prices", "compare"),
        ("Fact-check whether today's headline is correct", "fact_check"),
        ("Do a deep research on current AI agents", "deep"),
        ("আজকের AI খবর কী?", "search"),
        ("最新のAIニュースを教えて", "search"),
        ("Explain binary search algorithm", None),
        ("Write a poem about today", None),
        ("Please summarize my uploaded document today", None),
        ("What are the latest jobs? Do not use web.", None),
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
    def mock_research(question, *, max_sources, mode, provider):
        calls.append((question, max_sources, mode))
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
    assert calls == [("What are the latest AI developments?", 5, "search")]
    assert "[W1]" in result.content
    assert "[Source  untrusted  markdown ](https://example.org/report)" in result.content
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
