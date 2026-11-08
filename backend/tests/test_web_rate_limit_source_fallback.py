"""No paid requests: public Web Research when Groq synthesis is throttled."""
from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import settings
from app.llms import registry
from app.llms.types import (
    LLMGeneration, LLMProviderRateLimitError, LLMProviderRequestError,
)
from app.services import web_research_service as web
from app.services.web_research_service import research_web


def public_http(request):
    assert request.url.host == "api.tavily.com"
    if request.url.path == "/search":
        return httpx.Response(200, json={"results": [
            {"url": "https://example.org/japan/weather",
             "title": "Japan weather office",
             "raw_content": "Current public observations for Japanese cities."},
        ]})
    return httpx.Response(200, json={"results": []})


class Throttled:
    def generate(self, **kwargs):
        raise LLMProviderRateLimitError("Groq 429 synthetic test only")


class GoodAlternate:
    def __init__(self):
        self.calls = []

    def generate(self, *, instructions, input_text):
        self.calls.append((instructions, input_text))
        assert "UNTRUSTED" in instructions
        return LLMGeneration(
            text="The source contains public city observations [W1].",
            provider_name="fallback-test", model_name="alternate-test",
        )


@pytest.fixture
def public_web(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "fake-ci-only-key")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")


def test_cited_source_only_message_when_explicit_model_rate_limited(public_web):
    with httpx.Client(transport=httpx.MockTransport(public_http)) as client:
        result = research_web(
            "What is the weather in Tokyo?",
            max_sources=2,
            client=client,
            provider=Throttled(),
        )
    assert result.provider_name == "aqlyra-web-evidence-only"
    assert result.model_name == "source-links-only-v1"
    assert "rate-limited" in result.answer
    assert "observations" not in result.answer
    assert "[W1]" in result.answer
    assert result.sources[0].url == "https://example.org/japan/weather"


def test_bounded_second_groq_model_produces_cited_answer(
    public_web, monkeypatch,
):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-120b")
    primary = Throttled()
    alternate = GoodAlternate()
    monkeypatch.setattr(web, "create_latency_bounded_web_provider", lambda: primary)
    monkeypatch.setattr(web, "create_bounded_web_fallback_provider", lambda: alternate)
    with httpx.Client(transport=httpx.MockTransport(public_http)) as client:
        result = research_web(
            "What is the weather in Tokyo?", max_sources=2, client=client,
        )
    assert result.provider_name == "fallback-test"
    assert result.model_name == "alternate-test"
    assert result.answer.endswith("[W1].")
    assert len(alternate.calls) == 1


def test_second_model_429_fails_safely_to_sources(public_web, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(web, "create_latency_bounded_web_provider", Throttled)
    monkeypatch.setattr(web, "create_bounded_web_fallback_provider", Throttled)
    with httpx.Client(transport=httpx.MockTransport(public_http)) as client:
        result = research_web(
            "What is the weather in Tokyo?", max_sources=2, client=client,
        )
    assert result.provider_name == "aqlyra-web-evidence-only"
    assert result.answer.endswith("[W1]")


def test_non_throttle_failure_not_mislabelled_as_success(public_web):
    class Failed:
        def generate(self, **kwargs):
            raise LLMProviderRequestError("Provider network failure")

    with httpx.Client(transport=httpx.MockTransport(public_http)) as client:
        with pytest.raises(LLMProviderRequestError):
            research_web("What is the weather in Tokyo?", client=client, provider=Failed())


def test_alternate_factory_only_uses_public_mode_opt_in(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-ci-only-key")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "WEB_RESEARCH_GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "WEB_RESEARCH_GROQ_FALLBACK_ENABLED", False)
    assert registry.create_bounded_web_fallback_provider() is None
    monkeypatch.setattr(settings, "WEB_RESEARCH_GROQ_FALLBACK_ENABLED", True)
    captures = []
    monkeypatch.setattr(
        registry, "create_llm_provider",
        lambda **kwargs: captures.append(kwargs) or SimpleNamespace(info="public-only"),
    )
    alternate = registry.create_bounded_web_fallback_provider()
    assert alternate.info == "public-only"
    assert captures[0]["max_retries"] == 0
    assert captures[0]["model_name"] == "openai/gpt-oss-20b"
    assert captures[0]["max_output_tokens"] <= 700
    assert captures[0]["reasoning_effort"] is None


def test_source_only_notice_respects_bengali_and_japanese(public_web):
    for question, marker in [
        ("জাপানের আবহাওয়া কেমন?", "উৎসগুলো দেখুন"),
        ("日本の天気は？", "出典"),
    ]:
        with httpx.Client(transport=httpx.MockTransport(public_http)) as client:
            response = research_web(
                question, client=client, provider=Throttled(),
            )
        assert marker in response.answer
        assert response.answer.endswith("[W1]")
