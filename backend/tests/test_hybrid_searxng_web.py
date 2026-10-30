"""Keyless SearXNG-first public web research: provider and privacy regression."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.config.settings import settings
from app.llms.types import LLMGeneration
from app.services import chat_service
from app.services.searxng_provider import (
    configured_searxng_url, search_searxng,
)
from app.services.safe_web_reader import resolve_public_ipv4
from app.services.smart_web_router import route_web_request
from app.services.web_research_capability import public_web_research_status
from app.services.web_research_service import (
    WebResearchEvidenceError, WebResearchUnavailable, research_web,
)


class FakeGroundingModel:
    def __init__(self, answer="A confirmed source-backed claim [W1]."):
        self.answer = answer
        self.received = None

    def generate(self, *, instructions, input_text):
        self.received = json.loads(input_text)
        assert "UNTRUSTED" in instructions
        return LLMGeneration(
            text=self.answer, provider_name="mock-llm", model_name="mock",
        )


def prepare(monkeypatch, *, mode="auto", tavily=""):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "SEARXNG_BASE_URL", "https://searxng.example.org")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", mode)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", tavily)
    monkeypatch.setattr(settings, "SEARXNG_READ_PAGES_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "production")


def fake_search(request):
    assert request.url.host == "searxng.example.org"
    assert request.url.path == "/search"
    assert request.url.params["format"] == "json"
    assert request.url.params["safesearch"] == "1"
    assert "Authorization" not in request.headers
    return httpx.Response(200, json={"results": [
        {"title": "Official bulletin", "url": "https://www.example.gov.jp/news",
         "content": "Official publication with a stated 2026-10-31 date."},
        {"title": "Private network", "url": "https://127.0.0.1/secrets",
         "content": "internal"},
        {"title": "Official bulletin again", "url": "https://www.example.gov.jp/news",
         "content": "duplicate"},
        {"title": "Independent news", "url": "https://example.org/report",
         "content": "Another independently published claim."},
    ]})


def test_keyless_provider_search_and_source_citations(monkeypatch):
    prepare(monkeypatch)
    assert public_web_research_status() == "searxng_configured_unverified"
    model = FakeGroundingModel()
    with httpx.Client(transport=httpx.MockTransport(fake_search)) as client:
        result = research_web(
            "What was published today?", client=client, provider=model,
            max_sources=3,
        )
    assert len(result.sources) == 2
    assert [s.citation for s in result.sources] == ["[W1]", "[W2]"]
    assert "127.0.0.1" not in str(model.received)
    assert result.answer.endswith("[W1].")
    assert "Search result excerpt only" in model.received[
        "retrieved_public_evidence"
    ][0]["excerpt"]


def test_auto_router_uses_keyless_configured_search(monkeypatch):
    prepare(monkeypatch)
    assert route_web_request(
        "Who is the prime minister of Japan?", "auto",
    ) == "search"
    assert route_web_request("Explain binary search", "auto") is None
    assert route_web_request(
        "Who is the prime minister of Japan?", "off",
    ) is None


def test_failing_searxng_falls_back_to_configured_tavily(monkeypatch):
    prepare(monkeypatch, tavily="only-in-test")
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.host == "searxng.example.org":
            return httpx.Response(503)
        assert request.url.host == "api.tavily.com"
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{
                "url": "https://example.org/report", "title": "A source",
            }]})
        return httpx.Response(200, json={"results": [{
            "url": "https://example.org/report",
            "raw_content": "Verified current public source",
        }]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = research_web(
            "latest market source", client=client, provider=FakeGroundingModel(),
        )
    assert len(result.sources) == 1
    assert paths == ["/search", "/search", "/extract"]


def test_searxng_only_fail_closed_and_no_tavily_fallback(monkeypatch):
    prepare(monkeypatch, mode="searxng", tavily="test")
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(429),
    )) as client:
        with pytest.raises(WebResearchUnavailable):
            research_web("latest market news", client=client,
                         provider=FakeGroundingModel())


def test_no_fabricated_or_unapproved_source_links(monkeypatch):
    prepare(monkeypatch)
    with httpx.Client(transport=httpx.MockTransport(fake_search)) as client:
        for answer in ["No citations", "Unsupported [W99].",
                       "Read https://malicious.example.com [W1]."]:
            with pytest.raises(WebResearchEvidenceError):
                research_web("live news?", client=client,
                             provider=FakeGroundingModel(answer))


def test_malformed_json_html_and_private_urls_fail_closed(monkeypatch):
    prepare(monkeypatch)
    for response in (
        httpx.Response(200, text="<html>Captcha</html>"),
        httpx.Response(200, json={"results": [{"url": "http://127.0.0.1"}]}),
        httpx.Response(200, content=b"x" * 800001),
    ):
        with httpx.Client(transport=httpx.MockTransport(
            lambda req, response=response: response,
        )) as client:
            with pytest.raises((WebResearchUnavailable, WebResearchEvidenceError)):
                research_web("latest statistics", client=client,
                             provider=FakeGroundingModel())


def test_searxng_base_is_not_user_supplied_or_internal(monkeypatch):
    for raw in (
        "http://searxng.example.org", "https://localhost",
        "https://127.0.0.1", "https://metadata.google.internal",
        "https://user:pass@searxng.example.org",
        "https://searxng.example.org:1234",
        "https://searxng.example.org/path",
        "https://searxng.example.org?x=1",
    ):
        monkeypatch.setattr(settings, "SEARXNG_BASE_URL", raw)
        assert configured_searxng_url() is None


def test_private_dns_preflight_blocks_all_answers(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **kw: [
                            (socket.AF_INET, socket.SOCK_STREAM, 6, "",
                             ("9.9.9.9", 443)),
                            (socket.AF_INET, socket.SOCK_STREAM, 6, "",
                             ("127.0.0.1", 443)),
                        ])
    assert resolve_public_ipv4("example.org") is None


def test_page_reader_off_by_default(monkeypatch):
    prepare(monkeypatch)
    from app.services import safe_web_reader
    monkeypatch.setattr(
        safe_web_reader, "fetch_public_page",
        lambda url: pytest.fail("Page reader must not run by default"),
    )
    with httpx.Client(transport=httpx.MockTransport(fake_search)) as client:
        research_web("What is the latest report?", client=client,
                     provider=FakeGroundingModel())


def test_normal_converse_uses_searxng_without_private_history(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(
        chat_service, "get_recent_messages_for_conversation",
        lambda **kw: pytest.fail("Chat history cannot leave Aqlyra"),
    )
    monkeypatch.setattr(
        chat_service, "_retrieve_normal_chat_memories",
        lambda **kw: pytest.fail("Private memory cannot leave Aqlyra"),
    )
    observed = []
    def fake_research(q, **kwargs):
        observed.append(q)
        return SimpleNamespace(
            answer="Public claim backed [W1].", provider_name="test",
            model_name="test", sources=[SimpleNamespace(
                citation="[W1]", title="Public article",
                url="https://example.org/report",
            )],
        )
    monkeypatch.setattr(chat_service, "research_web", fake_research)
    result = chat_service.execute_chat_turn(
        db=Mock(), conversation=SimpleNamespace(
            mode="normal", user_id="test", id="c",
        ), message="Who is the prime minister of Japan?", web_mode="auto",
    )
    assert "official government source" in observed[0]
    assert "[W1]" in result.content
