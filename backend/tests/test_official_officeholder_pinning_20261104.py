"""Screenshot regression: source ranking cannot hide the official primary page.

All provider responses and officeholder names are synthetic. No live provider
credits, production accounts or historical politician assumptions.
"""
import json

import httpx
import pytest

from app.config.settings import settings
from app.llms.types import LLMGeneration
from app.services.public_office_guard import officeholder_search_query
from app.services.web_research_service import (
    WebResearchEvidenceError,
    research_web,
)


OFFICIAL_URL = "https://www.whitehouse.gov/administration/"


class EchoSourceProvider:
    def __init__(self):
        self.body = None

    def generate(self, *, instructions, input_text):
        self.body = json.loads(input_text)
        assert "untrusted" in instructions.lower()
        return LLMGeneration(
            text="The official page verifies the incumbent [W1].",
            provider_name="mock-web",
            model_name="mock-web-v1",
        )


def test_website_incumbent_is_pinned_even_when_search_returns_unrelated_items(
    monkeypatch,
):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-key")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    requested = []

    def transport(request: httpx.Request):
        body = json.loads(request.content)
        requested.append((request.url.path, body))
        if request.url.path == "/search":
            assert body["include_domains"] == ["whitehouse.gov"]
            assert "time_range" not in body
            return httpx.Response(200, json={"results": [
                {
                    "url": "https://news.example.org/off-topic-election",
                    "title": "Off-topic election news",
                    "raw_content": "This is not about the president.",
                },
                {
                    "url": "https://www.whitehouse.gov/releases/2026/11/other-topic/",
                    "title": "Other federal administration story",
                    "raw_content": "Other administration announcement.",
                },
            ]})
        assert request.url.path == "/extract"
        assert OFFICIAL_URL in body["urls"]
        return httpx.Response(200, json={"results": [
            {
                "url": OFFICIAL_URL,
                "raw_content": (
                    "# The Administration\n"
                    "## President Synthetic Test Person\n"
                    "Current President of the United States"
                ),
            }
        ]})

    provider = EchoSourceProvider()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = research_web(
            officeholder_search_query("Who is the current US president?"),
            include_domains=["whitehouse.gov"],
            time_range=None,
            max_sources=5,
            client=client,
            provider=provider,
        )
    assert result.sources[0].url == OFFICIAL_URL
    assert "President Synthetic Test Person" in result.sources[0].excerpt
    assert "news.example.org" not in json.dumps(provider.body)
    assert provider.body["retrieved_public_evidence"][0]["url"] == OFFICIAL_URL
    assert result.answer.endswith("[W1].")
    assert [path for path, _ in requested] == ["/search", "/extract"]


def test_no_official_page_content_fails_closed_even_if_search_is_empty(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-key")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    def transport(request: httpx.Request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": []})
        assert json.loads(request.content)["urls"] == [OFFICIAL_URL]
        return httpx.Response(200, json={"results": []})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(WebResearchEvidenceError, match="No readable"):
            research_web(
                officeholder_search_query("Who is the current US president?"),
                include_domains=["whitehouse.gov"],
                max_sources=5,
                client=client,
                provider=EchoSourceProvider(),
            )
