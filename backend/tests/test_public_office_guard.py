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


def test_country_only_followup_routes_to_sources_and_excludes_history(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-only-key")
    previous = [
        SimpleNamespace(role="user", content="Who's the prime minister?"),
        SimpleNamespace(role="assistant", content="Which country do you mean?"),
    ]
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: previous,
    )
    observed = []
    def fake_web(question, **kwargs):
        observed.append(question)
        return SimpleNamespace(
            answer="The incumbent was verified [W1].",
            sources=[SimpleNamespace(
                citation="[W1]", title="Official government",
                url="https://example.org/official",
            )],
            provider_name="test", model_name="stub",
        )
    monkeypatch.setattr(chat_service, "research_web", fake_web)
    result = chat_service.execute_chat_turn(
        db=Mock(),
        conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
        message="Bangladesh",
    )
    assert len(observed) == 1
    assert observed[0].startswith("Who is the prime minister of Bangladesh?")
    assert "Who's the prime minister?" not in observed[0]
    assert "https://example.org/official" in result.content


def test_unrelated_country_word_never_rebinds_private_conversation(monkeypatch):
    previous = [
        SimpleNamespace(role="user", content="Explain the Bangladesh flag."),
        SimpleNamespace(role="assistant", content="A flag description."),
    ]
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: previous,
    )
    question = chat_service.resolve_public_office_followup(
        db=Mock(), conversation=SimpleNamespace(id="c"), message="Japan",
    )
    assert question == "Japan"


def test_country_followup_requires_exact_assistant_guard(monkeypatch):
    previous = [
        SimpleNamespace(role="user", content="Who's the prime minister?"),
        SimpleNamespace(role="assistant", content="I guessed a country."),
    ]
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: previous,
    )
    assert chat_service.resolve_public_office_followup(
        db=Mock(), conversation=SimpleNamespace(id="c"),
        message="United Kingdom",
    ) == "United Kingdom"


def test_followup_with_live_web_disabled_returns_uncertainty(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(chat_service, "get_recent_messages_for_conversation",
                        lambda **kw: [
                            SimpleNamespace(role="user", content="Who's the prime minister?"),
                            SimpleNamespace(role="assistant", content="Which country do you mean?"),
                        ])
    result = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
        message="Bangladesh",
    )
    assert "can't verify" in result.content
    assert result.provider_name == "aqlyra-public-fact-guard"


@pytest.mark.parametrize("unsafe_reply", [
    "my API key", "private token", "secret", "password",
])
def test_sensitive_text_not_misinterpreted_as_public_country(monkeypatch, unsafe_reply):
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: pytest.fail("Sensitive text must not inspect/publicly rebind"),
    )
    assert chat_service.resolve_public_office_followup(
        db=Mock(), conversation=SimpleNamespace(id="c"),
        message=unsafe_reply,
    ) == unsafe_reply


@pytest.mark.parametrize("question", [
    "prime minister nam",
    "Prime Minister Name",
    "pm nam",
    "prime minister",
    "president nam",
])
def test_romanized_bangla_officeholder_asks_for_country_without_groq(monkeypatch, question):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(chat_service, "create_configured_llm_provider",
                        lambda: pytest.fail("Never guess current public office"))
    assert is_public_officeholder_question(question)
    assert is_ambiguous_public_officeholder_question(question)
    assert smart_web_router.route_web_request(question) is None
    reply = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
        message=question, web_mode="auto",
    )
    assert reply.content == "Which country do you mean?"
    assert reply.provider_name == "aqlyra-public-fact-guard"


@pytest.mark.parametrize("question", [
    "prime minister name of Japan",
    "prime minister of Japan",
    "japan prime minister nam",
    "president of Bangladesh",
])
def test_country_named_romanized_query_requires_sources(monkeypatch, question):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "fake-test-only")
    assert is_public_officeholder_question(question)
    assert not is_ambiguous_public_officeholder_question(question)
    assert smart_web_router.route_web_request(question) == "search"


def test_actual_incident_romanized_prompt_followed_by_japan_then_bd(monkeypatch):
    """Post-release user scenario, without revealing private chat to search."""
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    first = [
        SimpleNamespace(role="user", content="prime minister nam"),
        SimpleNamespace(
            role="assistant",
            content="I’m not sure which country you’re referring to. "
                    "Could you let me know which country’s prime minister "
                    "you’re asking about?",
        ),
    ]
    second = first + [
        SimpleNamespace(role="user", content="japan"),
        SimpleNamespace(
            role="assistant",
            content="The current Prime Minister of Japan is Fumio Kishida.",
        ),
    ]
    turns = [("japan", first, "Japan"), ("bd", second, "Bangladesh")]
    for message, preceding, country in turns:
        monkeypatch.setattr(
            chat_service, "get_recent_messages_for_conversation",
            lambda **kwargs: preceding,
        )
        query = chat_service.resolve_public_office_followup(
            db=Mock(), conversation=SimpleNamespace(id="c"), message=message,
        )
        assert query == f"Who is the prime minister of {country}?"
        result = chat_service.execute_chat_turn(
            db=Mock(), conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
            message=message, web_mode="auto",
        )
        assert result.provider_name == "aqlyra-public-fact-guard"
        assert "can't verify" in result.content
        assert "Sheikh Hasina" not in result.content
        assert "Fumio Kishida" not in result.content


def test_romanized_followup_source_query_does_not_contain_chat_history(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "fake-test-only")
    previous = [
        SimpleNamespace(role="user", content="prime minister nam"),
        SimpleNamespace(role="assistant", content="Which country do you mean?"),
    ]
    monkeypatch.setattr(chat_service, "get_recent_messages_for_conversation",
                        lambda **kwargs: previous)
    queries = []

    def fake_research(query, **kwargs):
        queries.append(query)
        return SimpleNamespace(
            answer="Current leader confirmed [W1].",
            sources=[SimpleNamespace(citation="[W1]", title="Government",
                                     url="https://example.org/current")],
            provider_name="fake-web", model_name="fake",
        )

    monkeypatch.setattr(chat_service, "research_web", fake_research)
    response = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
        message="bd", web_mode="auto",
    )
    assert len(queries) == 1
    assert queries[0].startswith("Who is the prime minister of Bangladesh?")
    assert "prime minister nam" not in queries[0]
    assert "[W1]" in response.content


def test_romanized_converse_stream_never_calls_groq_for_unspecified_country(monkeypatch):
    monkeypatch.setattr(chat_service, "create_configured_llm_provider",
                        lambda: pytest.fail("No Groq call for current officeholder"))
    events = list(chat_service.stream_normal_chat_reply(
        db=Mock(), conversation=SimpleNamespace(id="c", user_id="u"),
        message="prime minister nam",
    ))
    assert [event.event_type for event in events] == ["delta", "complete"]
    assert events[0].delta_text == "Which country do you mean?"


def test_unrelated_followup_not_reinterpreted_as_country_without_office_context(monkeypatch):
    monkeypatch.setattr(chat_service, "get_recent_messages_for_conversation",
                        lambda **kwargs: [
                            SimpleNamespace(role="user", content="How is weather?"),
                            SimpleNamespace(role="assistant", content="Which city?"),
                        ])
    assert chat_service.resolve_public_office_followup(
        db=Mock(), conversation=SimpleNamespace(id="c"), message="bd",
    ) == "bd"


def test_switch_does_not_leak_credentials_from_prior_topic(monkeypatch):
    monkeypatch.setattr(chat_service, "get_recent_messages_for_conversation",
                        lambda **kwargs: [
                            SimpleNamespace(role="user", content="prime minister nam"),
                            SimpleNamespace(role="assistant", content="Which country do you mean?"),
                            SimpleNamespace(role="user", content="my password"),
                            SimpleNamespace(role="assistant", content="prime minister?"),
                        ])
    assert chat_service.resolve_public_office_followup(
        db=Mock(), conversation=SimpleNamespace(id="c"), message="bd",
    ) == "bd"


def test_country_switch_after_guarded_no_web_fallback(monkeypatch):
    """bd must remain public-office scoped after Japan's honest no-web reply."""
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    safe_reply = unverified_officeholder_reply(
        "Who is the prime minister of Japan?"
    )
    prior = [
        SimpleNamespace(role="user", content="prime minister nam"),
        SimpleNamespace(role="assistant", content="Which country do you mean?"),
        SimpleNamespace(role="user", content="japan"),
        SimpleNamespace(role="assistant", content=safe_reply),
    ]
    monkeypatch.setattr(chat_service, "get_recent_messages_for_conversation",
                        lambda **kw: prior)
    q = chat_service.resolve_public_office_followup(
        db=Mock(), conversation=SimpleNamespace(id="c"), message="bd",
    )
    assert q == "Who is the prime minister of Bangladesh?"
    result = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(mode="normal", id="c", user_id="u"),
        message="bd", web_mode="auto",
    )
    assert result.provider_name == "aqlyra-public-fact-guard"
    assert "can't verify" in result.content
