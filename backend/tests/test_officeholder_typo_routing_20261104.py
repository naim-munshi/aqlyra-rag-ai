"""Regression for screenshot: 'What is the name of us presodent'.

Only synthetic/offline checks; a correct current leader must come from verified
web evidence, never from a hardcoded name or a timeless LLM completion.
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
)


@pytest.mark.parametrize("question", [
    "What is the name of us presodent",
    "What is the name of the US president?",
    "What's the name of the USA presedent?",
    "Who is the presdent of the United States?",
    "What is the name of the UK presidant?",
    "What is the name of Japan's prime minister?",
])
def test_president_name_query_routes_to_verified_public_web(monkeypatch, question):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-testing-only")
    assert is_public_officeholder_question(question)
    assert not is_ambiguous_public_officeholder_question(question)
    assert smart_web_router.route_web_request(question, mode="auto") == "search"
    official_query = officeholder_search_query(question)
    assert "official government source" in official_query
    if "prime minister" not in question:
        assert "president" in official_query.casefold()
        assert "presodent" not in official_query.casefold()
        assert "presedent" not in official_query.casefold()


@pytest.mark.parametrize("question", [
    "What is the name of us presodent",
    "What's the name of the USA presedent?",
])
def test_no_search_available_refuses_outdated_president_guess(
    monkeypatch, question,
):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(
        chat_service, "create_configured_llm_provider",
        lambda: pytest.fail("This unsourced incumbent question reached the LLM"),
    )
    result = chat_service.execute_chat_turn(
        db=Mock(),
        conversation=SimpleNamespace(mode="normal", id="synthetic", user_id="test"),
        message=question,
        web_mode="auto",
    )
    assert result.provider_name == "aqlyra-public-fact-guard"
    assert "can't verify" in result.content.casefold()
    assert "Joe Biden" not in result.content
    assert "Donald Trump" not in result.content


def test_misspelled_question_uses_research_with_corrected_public_query(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-testing-only")
    received = []

    def fake_research(query, **options):
        received.append((query, options["mode"]))
        return SimpleNamespace(
            answer="Officeholder confirmed by official source [W1].",
            sources=[
                SimpleNamespace(
                    citation="[W1]",
                    title="Government record",
                    url="https://example.org/public",
                )
            ],
            provider_name="synthetic-web",
            model_name="synthetic-web-v1",
        )

    monkeypatch.setattr(chat_service, "research_web", fake_research)
    result = chat_service.execute_chat_turn(
        db=Mock(),
        conversation=SimpleNamespace(mode="normal", id="synthetic", user_id="test"),
        message="What is the name of us presodent",
        web_mode="auto",
    )
    assert len(received) == 1
    assert received[0][1] == "search"
    assert "president" in received[0][0]
    assert "presodent" not in received[0][0]
    assert "official government source" in received[0][0]
    assert "[W1]" in result.content
    assert "https://example.org/public" in result.content
    assert result.provider_name == "synthetic-web"


@pytest.mark.parametrize("question", [
    "Who was the presodent of the US in 2010?",
    "What is the name of the US presodent in 2000?",
    "Write a fictional poem about a presodent.",
    "Explain the duties of a president.",
])
def test_historical_and_evergreen_questions_not_misclassified(question):
    assert not is_public_officeholder_question(question)
    assert officeholder_search_query(question) == question


def test_ambiguous_misspelled_president_short_form_requests_country(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-testing-only")
    assert is_public_officeholder_question("presodent nam")
    assert is_ambiguous_public_officeholder_question("presodent nam")
    assert smart_web_router.route_web_request("presodent nam") is None
