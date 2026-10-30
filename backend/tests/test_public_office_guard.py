"""Screenshot regression: never guess a country or an unsourced incumbent.

Uses local stubs only; no live political names, paid LLM calls or network.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.config.settings import settings
from app.services import chat_service, smart_web_router
from app.services.public_office_guard import (
    is_ambiguous_public_officeholder_question,
    is_public_officeholder_question,
    officeholder_search_query,
    unverified_officeholder_reply,
)


@pytest.mark.parametrize("query", [
    "Who's the prime minister?",
    "Who’s the prime minister?",
    "Who is the current president?",
    "প্রধানমন্ত্রী কে?",
    "বর্তমান প্রধানমন্ত্রী কে?",
    "首相は誰？",
    "現在の首相は誰ですか？",
])
def test_unspecified_country_clarified_without_web_or_model(monkeypatch, query):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-only-key")
    assert is_public_officeholder_question(query)
    assert is_ambiguous_public_officeholder_question(query)
    assert smart_web_router.route_web_request(query, mode="auto") is None
    assert smart_web_router.route_web_request(query, mode="on") is None
    reply = unverified_officeholder_reply(query)
    assert reply is not None and len(reply) < 150


@pytest.mark.parametrize("query", [
    "Who is the prime minister of Bangladesh?",
    "Who’s Bangladesh's prime minister?",
    "Who is the current prime minister of Japan?",
    "বাংলাদেশের প্রধানমন্ত্রী কে?",
    "日本の首相は誰？",
])
def test_explicit_country_requires_live_search_in_auto(monkeypatch, query):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-only-key")
    assert is_public_officeholder_question(query)
    assert not is_ambiguous_public_officeholder_question(query)
    assert smart_web_router.route_web_request(query) == "search"
    assert "official government source" in officeholder_search_query(query)


@pytest.mark.parametrize("query", [
    "Explain what a prime minister does.",
    "Who was the prime minister of Bangladesh in 2010?",
    "Write a poem about a president.",
    "What is a parliamentary election?",
    "Who created the prime minister's website?",
])
def test_evergreen_and_explicit_historical_requests_not_blocked(query):
    assert not is_public_officeholder_question(query)
    assert unverified_officeholder_reply(query) is None
    assert officeholder_search_query(query) == query


def test_missing_tavily_key_never_calls_paid_llm_or_guesses(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "TAVILY_KEYLESS_ENABLED", False)
    monkeypatch.setattr(
        chat_service, "create_configured_llm_provider",
        lambda: pytest.fail("Unverified live question reached generic LLM"),
    )
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: pytest.fail("No private history required for current public office"),
    )
    context = SimpleNamespace(mode="normal", user_id="test", id="conversation")
    result = chat_service.execute_chat_turn(
        db=Mock(), conversation=context,
        message="Who is the prime minister of Bangladesh?",
        web_mode="auto",
    )
    assert "can't verify" in result.content
    assert result.provider_name == "aqlyra-public-fact-guard"
    assert "Sheikh Hasina" not in result.content


def test_off_mode_stays_off_and_never_guesses_even_with_tavily_key(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-only-key")
    monkeypatch.setattr(
        chat_service, "create_configured_llm_provider",
        lambda: pytest.fail("No unsourced political fact generation"),
    )
    response = chat_service.execute_chat_turn(
        db=Mock(),
        conversation=SimpleNamespace(mode="normal", user_id="x", id="c"),
        message="Who is the prime minister of Bangladesh?",
        web_mode="off",
    )
    assert "can't verify" in response.content


def test_auto_live_question_research_uses_only_current_question(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-only-key")
    questions = []
    def mock_research(question, **options):
        questions.append((question, options))
        return SimpleNamespace(
            answer="Source-verified officeholder [W1].",
            sources=[SimpleNamespace(
                citation="[W1]", title="Official cabinet",
                url="https://example.org/cabinet",
            )],
            provider_name="mock-web", model_name="mock-model",
        )
    monkeypatch.setattr(chat_service, "research_web", mock_research)
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: pytest.fail("Private chat history must not be sent to web"),
    )
    result = chat_service.execute_chat_turn(
        db=Mock(),
        conversation=SimpleNamespace(mode="normal", id="private", user_id="secret"),
        message="Who is the prime minister of Bangladesh?", web_mode="auto",
    )
    assert len(questions) == 1
    assert questions[0][0].startswith("Who is the prime minister of Bangladesh?")
    assert "official government source" in questions[0][0]
    assert "https://example.org/cabinet" in result.content
    assert "[W1]" in result.content


def test_streaming_guard_has_normal_delta_and_complete_contract(monkeypatch):
    monkeypatch.setattr(
        chat_service, "create_configured_llm_provider",
        lambda: pytest.fail("No LLM should be called"),
    )
    events = list(chat_service.stream_normal_chat_reply(
        db=Mock(), conversation=SimpleNamespace(id="c",user_id="u"),
        message="Who's the prime minister?",
    ))
    assert [event.event_type for event in events] == ["delta", "complete"]
    assert events[0].delta_text == "Which country do you mean?"
    assert events[1].generation.text == events[0].delta_text


def test_bangla_and_japanese_no_web_are_honest(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    for prompt, fragment in [
        ("বাংলাদেশের প্রধানমন্ত্রী কে?", "লাইভ"),
        ("日本の首相は誰？", "ライブ"),
    ]:
        result = chat_service.execute_chat_turn(
            db=Mock(), conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
            message=prompt, web_mode="auto",
        )
        assert fragment in result.content
