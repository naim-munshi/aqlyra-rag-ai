"""Live web research contract using mocked Tavily network; no live credits."""
import json
import re

from fastapi.testclient import TestClient
import httpx
import pytest

from app.config.settings import settings
from app.llms.types import LLMGeneration
from app.services.web_research_service import (
    WebResearchEvidenceError,
    WebResearchUnavailable,
    research_web,
    safe_public_url,
)
import app.api.web_research as api


class StubProvider:
    def __init__(self, text: str = "Verified from the page [W1].") -> None:
        self.text = text
        self.received = None

    def generate(self, *, instructions: str, input_text: str) -> LLMGeneration:
        self.received = json.loads(input_text)
        assert "UNTRUSTED" in instructions
        return LLMGeneration(
            text=self.text, provider_name="stub", model_name="test-model",
        )


def fake_tavily(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "api.tavily.com"
    assert request.headers["authorization"] == "Bearer test-web-key"
    data = json.loads(request.content)
    if request.url.path == "/search":
        assert "include_raw_content" in data
        return httpx.Response(200, json={"results": [
            {"url": "https://example.com/article", "title": "Example article"},
            {"url": "http://127.0.0.1/secrets", "title": "Private IP"},
            {"url": "https://example.com/article", "title": "Duplicate"},
            {"url": "https://example.org/report", "title": "Report", "published_date": "2026-10-25"},
        ]})
    assert request.url.path == "/extract"
    assert data["urls"] == [
        "https://example.com/article", "https://example.org/report"
    ]
    return httpx.Response(200, json={"results": [
        {"url": "https://example.com/article", "raw_content": "Current figures and facts from a real page."},
        {"url": "https://example.org/report", "raw_content": "A second independent report."},
    ]})


def test_public_url_validation() -> None:
    for url in [
        "http://example.com",
        "https://127.0.0.1/private",
        "https://localhost/private",
        "https://192.168.1.1/",
        "https://10.0.0.1/",
        "https://example.local/data",
        "https://example.org:3000/",
        "file:///etc/passwd",
        "https://example.org@127.0.0.1/",
    ]:
        assert safe_public_url(url) is None
    assert safe_public_url("https://example.org/report") is not None


def test_search_extract_cited_generation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    provider = StubProvider("The source supports this answer [W1] and [W2].")
    with httpx.Client(transport=httpx.MockTransport(fake_tavily)) as client:
        result = research_web(
            "What are the latest research figures?",
            max_sources=3,
            client=client,
            provider=provider,
        )
    assert len(result.sources) == 2
    assert result.sources[0].citation == "[W1]"
    assert result.sources[1].citation == "[W2]"
    assert result.sources[1].published_date == "2026-10-25"
    assert result.answer.endswith("[W2].")
    assert len(provider.received["retrieved_public_evidence"]) == 2
    assert "secrets" not in str(provider.received)


def test_rejects_fabricated_citations(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    with httpx.Client(transport=httpx.MockTransport(fake_tavily)) as client:
        with pytest.raises(WebResearchEvidenceError):
            research_web("current news", client=client, provider=StubProvider("Claims [W99]."))
        with pytest.raises(WebResearchEvidenceError):
            research_web("current news", client=client, provider=StubProvider("No citations."))


def test_provider_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    with pytest.raises(WebResearchUnavailable):
        research_web("current news", provider=StubProvider())
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    with pytest.raises(WebResearchUnavailable):
        research_web("current news", provider=StubProvider())


def test_agent_never_returns_unextracted_snippets(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    def transport(request: httpx.Request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [
                {"url": "https://example.com/article", "title": "Page", "content": "Search snippet"},
            ]})
        return httpx.Response(200, json={"results": [], "failed_results": []})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(WebResearchEvidenceError):
            research_web("current figures", client=client, provider=StubProvider())


def test_web_endpoint_requires_auth_and_valid_body(client: TestClient) -> None:
    response = client.post("/api/v1/web/research", json={
        "question": "Give current news",
    })
    assert response.status_code == 401
    assert client.post("/api/v1/web/research", json={
        "question": "x",
    }).status_code in {401, 422}


def test_authenticated_web_endpoint(client: TestClient, monkeypatch) -> None:
    registered = client.post("/api/v1/auth/register", json={
        "username": "webresearchuser",
        "email": "webresearch@example.com",
        "password": "StrongPassword321!",
    })
    assert registered.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "email": "webresearch@example.com",
        "password": "StrongPassword321!",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    from app.schemas.web_research import WebResearchResponse, WebResearchSource
    from datetime import datetime, timezone
    monkeypatch.setattr(api, "research_web", lambda question, max_sources: WebResearchResponse(
        question=question,
        answer="Evidence-backed result [W1].",
        sources=[WebResearchSource(
            citation="[W1]", title="Source", url="https://example.com",
            excerpt="Evidence", published_date=None,
        )],
        provider_name="stub", model_name="test",
        searched_at=datetime.now(timezone.utc),
    ))
    response = client.post("/api/v1/web/research", json={
        "question": "Describe the facts", "max_sources": 3,
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["citation"] == "[W1]"
    assert client.post("/api/v1/web/research", json={
        "question": "x", "max_sources": 100,
    }, headers={"Authorization": f"Bearer {token}"}).status_code == 422


def test_malformed_provider_source_url_does_not_crash(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    def transport(request: httpx.Request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [
                {"url": "https://example.com/page", "title": "Page"},
            ]})
        return httpx.Response(200, json={"results": [
            {"url": ["unexpected", "list"], "raw_content": "bad"},
            {"url": "https://example.com/page", "raw_content": "Real content"},
        ]})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        response = research_web(
            "public research", client=client, provider=StubProvider()
        )
    assert len(response.sources) == 1
