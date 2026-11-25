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
    monkeypatch.setattr(api, "research_web", lambda question, max_sources, **kwargs: WebResearchResponse(
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


def test_explicit_keyless_mode_is_local_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "TAVILY_KEYLESS_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    def transport(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        assert request.headers["x-tavily-access-mode"] == "keyless"
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [
                {"url": "https://example.com/page", "title": "News"}
            ]})
        return httpx.Response(200, json={"results": [
            {"url": "https://example.com/page", "raw_content": "Fresh public data"}
        ]})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        answer = research_web("latest updates", client=client, provider=StubProvider())
    assert answer.sources[0].citation == "[W1]"
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(WebResearchUnavailable):
        research_web("latest updates", provider=StubProvider())


def test_deep_research_uses_advanced_search_and_extraction(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    steps: list[str] = []

    def transport(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        steps.append(request.url.path)
        if request.url.path == "/search":
            assert body["search_depth"] == "advanced"
            return httpx.Response(200, json={"results": [
                {"url": "https://example.com/deep", "title": "Deep source"},
            ]})
        assert body["extract_depth"] == "advanced"
        return httpx.Response(200, json={"results": [
            {"url": "https://example.com/deep", "raw_content": "In-depth evidence"},
        ]})

    model = StubProvider()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        answer = research_web("Give a detailed report", mode="deep", client=client, provider=model)
    assert steps == ["/search", "/extract"]
    assert model.received["research_mode"] == "deep"
    assert answer.sources[0].citation == "[W1]"


def test_url_mode_uses_tavily_extract_only_and_rejects_local_urls(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    paths: list[str] = []

    def transport(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.url.path == "/extract"
        assert json.loads(request.content)["urls"] == ["https://example.org/article"]
        return httpx.Response(200, json={"results": [
            {"url": "https://example.org/article", "raw_content": "Public article text"},
        ]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        answer = research_web(
            "Summarize the attached webpage", mode="url",
            source_url="https://example.org/article", client=client,
            provider=StubProvider(),
        )
    assert paths == ["/extract"]
    assert len(answer.sources) == 1
    with pytest.raises(WebResearchEvidenceError):
        research_web(
            "Read private page", mode="url",
            source_url="https://127.0.0.1/admin", provider=StubProvider(),
        )


def test_request_validation_requires_url_only_in_url_mode(client: TestClient, monkeypatch) -> None:
    registered = client.post("/api/v1/auth/register", json={
        "username": "weburlresearchuser",
        "email": "weburlresearch@example.com",
        "password": "StrongPassword321!",
    })
    assert registered.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "email": "weburlresearch@example.com", "password": "StrongPassword321!",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/web/research", json={
        "question": "Read this", "mode": "url"
    }, headers=headers).status_code == 422
    assert client.post("/api/v1/web/research", json={
        "question": "Current research", "source_url": "https://example.com"
    }, headers=headers).status_code == 422
    assert client.post("/api/v1/web/research", json={
        "question": "Current research", "mode": "magic"
    }, headers=headers).status_code == 422


def test_time_and_domain_filters_enforced_after_search(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    calls: list[str] = []
    def provider(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(request.url.path)
        if request.url.path == "/search":
            assert body["time_range"] == "month"
            assert body["include_domains"] == ["python.org", "docs.python.org"]
            return httpx.Response(200, json={"results": [
                {"url": "https://evil.org/unrelated", "title": "Outside"},
                {"url": "https://notpython.org/fake", "title": "Lookalike"},
                {"url": "https://docs.python.org/3/library/asyncio.html", "title": "Asyncio"},
                {"url": "https://www.python.org/downloads/", "title": "Python downloads"},
            ]})
        assert body["urls"] == [
            "https://docs.python.org/3/library/asyncio.html",
            "https://www.python.org/downloads/",
        ]
        return httpx.Response(200, json={"results": [
            {"url": "https://docs.python.org/3/library/asyncio.html",
             "raw_content": "Asyncio API docs"},
            {"url": "https://www.python.org/downloads/",
             "raw_content": "Downloads and releases"},
        ]})

    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        result = research_web(
            "Latest Python documentation updates",
            mode="search",
            time_range="month",
            include_domains=["PYTHON.ORG", "docs.python.org"],
            provider=StubProvider("The official sources say this [W1] [W2]."),
            client=client,
        )
    assert len(result.sources) == 2
    assert calls == ["/search", "/extract"]
    assert all("python.org" in entry.url for entry in result.sources)


def test_compare_prefers_independent_web_domains(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")

    def provider(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [
                {"url": "https://a.example.org/one", "title": "One"},
                {"url": "https://a.example.org/two", "title": "Two"},
                {"url": "https://b.example.org/one", "title": "Three"},
                {"url": "https://c.example.org/one", "title": "Four"},
            ]})
        assert body["urls"] == [
            "https://a.example.org/one",
            "https://b.example.org/one",
            "https://c.example.org/one",
        ]
        return httpx.Response(200, json={"results": [
            {"url": url, "raw_content": "Independent extracted evidence"}
            for url in body["urls"]
        ]})

    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        result = research_web(
            "Compare the evidence", max_sources=3, mode="compare",
            client=client, provider=StubProvider("Compared independently [W1] [W2]."),
        )
    assert [x.citation for x in result.sources] == ["[W1]", "[W2]", "[W3]"]


def test_domain_validation_and_url_mode_filter_rejection() -> None:
    from pydantic import ValidationError
    from app.schemas.web_research import WebResearchRequest
    valid = WebResearchRequest(
        question="Research model serving",
        include_domains=[" ARXIV.ORG ", "pytorch.org"],
        time_range="week",
    )
    assert valid.include_domains == ["arxiv.org", "pytorch.org"]
    for domains in [
        ["http://arxiv.org"], ["arxiv.org/path"], ["*.arxiv.org"],
        ["localhost"], ["example.internal"], ["127.0.0.1"],
        ["docs.python.org", "docs.python.org"],
        ["a.org", "b.org", "c.org", "d.org"],
    ]:
        with pytest.raises(ValidationError):
            WebResearchRequest(question="Research", include_domains=domains)
    with pytest.raises(ValidationError):
        WebResearchRequest(
            question="Summarize webpage", mode="url",
            source_url="https://example.org", time_range="day",
        )


def test_iterative_deep_research_uses_two_searches_and_shared_source_budget(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    queries = []

    def transport(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        if request.url.path == "/search":
            queries.append(data["query"])
            domain = "example.com" if len(queries) == 1 else "example.org"
            return httpx.Response(200, json={"results": [
                {"url": f"https://{domain}/evidence", "title": "Source evidence"},
            ]})
        assert request.url.path == "/extract"
        assert set(data["urls"]) == {
            "https://example.com/evidence", "https://example.org/evidence",
        }
        return httpx.Response(200, json={"results": [
            {"url": url, "raw_content": "Verified public source evidence"}
            for url in data["urls"]
        ]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = research_web(
            "Deep research on AI deployment safety",
            mode="deep",
            max_sources=5,
            iterative=True,
            client=client,
            provider=StubProvider("Both sources agree [W1] [W2]."),
        )
    assert len(queries) == 2
    assert queries[0] != queries[1]
    assert len(result.sources) == 2
    assert [source.citation for source in result.sources] == ["[W1]", "[W2]"]

def test_untrusted_web_urls_and_model_invented_links_are_rejected(monkeypatch):
    assert safe_public_url("https://example.com/path" + chr(10) + "malicious") is None
    assert safe_public_url("https://example.com/path" + chr(9) + "malicious") is None
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-web-key")
    with httpx.Client(transport=httpx.MockTransport(fake_tavily)) as client:
        with pytest.raises(WebResearchEvidenceError, match="unapproved external links"):
            research_web(
                "What are the latest research figures?",
                max_sources=3, client=client,
                provider=StubProvider("An unsupported link [W1] https://phishing.example/bait"),
            )
