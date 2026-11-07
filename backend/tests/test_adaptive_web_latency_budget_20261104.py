"""Latency policy contracts without real Groq quota consumption."""

from types import SimpleNamespace
from unittest.mock import Mock

from app.config.settings import settings
from app.llms import registry
from app.services import chat_service


def test_groq_public_web_has_no_automatic_retry_loop(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "WEB_RESEARCH_LLM_MAX_RETRIES", 0)
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SECONDS", 60.0)
    monkeypatch.setattr(settings, "WEB_RESEARCH_LLM_TIMEOUT_SECONDS", 20.0)
    seen = []
    monkeypatch.setattr(
        registry, "create_llm_provider",
        lambda **kwargs: seen.append(kwargs) or SimpleNamespace(info="fake"),
    )
    result = registry.create_latency_bounded_web_provider()
    assert result.info == "fake"
    assert len(seen) == 1
    assert seen[0]["max_retries"] == 0
    assert seen[0]["timeout_seconds"] == 20.0
    assert seen[0]["provider_name"] == "groq"
    assert seen[0]["api_key"] == "synthetic-only"


def test_normal_chat_provider_keeps_its_independent_retry_budget(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "WEB_RESEARCH_LLM_MAX_RETRIES", 0)
    calls = []
    monkeypatch.setattr(
        registry, "create_llm_provider",
        lambda **kwargs: calls.append(kwargs) or SimpleNamespace(info="fake"),
    )
    registry.create_configured_llm_provider()
    assert calls[0]["max_retries"] == 2


def test_regular_and_deep_research_retains_expected_source_budgets(monkeypatch):
    captures = []

    def fake_search(query, **kwargs):
        captures.append(kwargs)
        return SimpleNamespace(
            answer="A source-backed response [W1].",
            sources=[
                SimpleNamespace(
                    citation="[W1]",
                    title="Synthetic source",
                    url="https://example.org/public",
                )
            ],
            provider_name="stub",
            model_name="stub",
        )

    monkeypatch.setattr(chat_service, "research_web", fake_search)
    chat_service.generate_web_chat_reply(
        message="Find current scholarships in Japan",
        research_mode="search",
    )
    chat_service.generate_web_chat_reply(
        message="Deep research on current scholarships in Japan",
        research_mode="deep",
    )
    assert captures[0]["max_sources"] == 3
    assert captures[1]["max_sources"] == 5
