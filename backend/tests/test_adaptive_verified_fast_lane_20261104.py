"""Deterministic fast-lane acceptance for public incumbents.

No live Tavily/Groq calls, no hardcoded person names, no private content.
"""
import json
from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import settings
from app.services import smart_web_router
from app.services.official_fact_fast_path import verified_officeholder_fast_answer
from app.services.public_office_guard import (
    is_public_officeholder_question,
    officeholder_authoritative_url,
    officeholder_primary_domains,
    officeholder_search_query,
)
from app.schemas.web_research import WebResearchSource
from app.services.web_research_service import (
    WebResearchEvidenceError,
    research_web,
)


def _source(url, excerpt):
    return WebResearchSource(
        citation="[W1]", title="Government administration",
        url=url, excerpt=excerpt, published_date=None,
    )


@pytest.mark.parametrize("question", [
    "tell me bd pm name",
    "Bangladesh prime minister name",
    "Who is the prime minister of Bangladesh?",
])
def test_bd_shorthand_recognizes_verified_public_fast_lane(monkeypatch, question):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-only")
    assert is_public_officeholder_question(question)
    assert smart_web_router.route_web_request(question, mode="auto") == "search"
    assert officeholder_primary_domains(question) == ["pmo.gov.bd", "cabinet.gov.bd"]
    assert officeholder_authoritative_url(question) == "https://pmo.gov.bd/"
    assert "Prime Minister of Bangladesh" in officeholder_search_query(question)


def test_extracted_official_page_returns_short_answer_without_model(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    calls = []

    def synthetic_tavily(request):
        payload = json.loads(request.content)
        calls.append((request.url.path, payload))
        if request.url.path == "/search":
            assert payload["include_domains"] == ["pmo.gov.bd", "cabinet.gov.bd"]
            assert "time_range" not in payload
            return httpx.Response(200, json={"results": [
                {"url": "https://news.example.org/outdated", "title": "Outdated"},
            ]})
        assert request.url.path == "/extract"
        assert payload["urls"][0] == "https://pmo.gov.bd/"
        return httpx.Response(200, json={"results": [
            {"url": "https://pmo.gov.bd/",
             "raw_content": "প্রধানমন্ত্রী\nজনাব কল্পিত পরীক্ষা\nপ্রধানমন্ত্রী\nগণপ্রজাতন্ত্রী বাংলাদেশ সরকার"}
        ]})

    with httpx.Client(transport=httpx.MockTransport(synthetic_tavily)) as client:
        result = research_web(
            officeholder_search_query("tell me bd pm name"),
            include_domains=["pmo.gov.bd", "cabinet.gov.bd"],
            max_sources=2,
            client=client,
        )
    assert result.provider_name == "aqlyra-official-fact"
    assert "কল্পিত পরীক্ষা" in result.answer
    assert result.answer.endswith("[W1]")
    assert [src.url for src in result.sources] == ["https://pmo.gov.bd/"]
    assert [path for path, _ in calls] == ["/search", "/extract"]


def test_us_primary_page_fast_answer_requires_extracted_text(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")

    def transport(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": []})
        assert json.loads(request.content)["urls"] == [
            "https://www.whitehouse.gov/administration/"
        ]
        return httpx.Response(200, json={"results": [
            {"url": "https://www.whitehouse.gov/administration/",
             "raw_content": "# The Administration\n## President Example Sample\nPresident of the United States"}
        ]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        response = research_web(
            officeholder_search_query("Who is the current US president?"),
            include_domains=["whitehouse.gov"],
            max_sources=2,
            client=client,
        )
    assert response.provider_name == "aqlyra-official-fact"
    assert response.answer == "The current U.S. president is Example Sample. [W1]"


def test_cached_search_result_alone_is_not_live_current_authority(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    def synthetic_tavily(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{
                "url": "https://www.whitehouse.gov/administration/",
                "title": "Government",
                "raw_content": "## President Stale Incorrect",
            }]})
        assert request.url.path == "/extract"
        return httpx.Response(200, json={"results": []})
    with httpx.Client(transport=httpx.MockTransport(synthetic_tavily)) as client:
        with pytest.raises(WebResearchEvidenceError, match="extracted government"):
            research_web(
                officeholder_search_query("Who is the current US president?"),
                include_domains=["whitehouse.gov"],
                client=client,
            )


def test_wrong_page_role_does_not_become_a_fast_answer():
    url = "https://pmo.gov.bd/"
    source = _source(url, "জনাব কল্পিত পরীক্ষা\nপ্রাক্তন প্রধানমন্ত্রী")
    assert verified_officeholder_fast_answer(
        "Who is the prime minister of Bangladesh?",
        [source],
        extracted_urls={url},
    ) is None
    assert verified_officeholder_fast_answer(
        "Who is the prime minister of Bangladesh?",
        [_source("https://example.org/fake", "জনাব কল্পিত পরীক্ষা\nপ্রধানমন্ত্রী")],
        extracted_urls={"https://example.org/fake"},
    ) is None


def test_live_style_government_page_after_navigation_and_honorific(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    long_page = (
        "নোটিশ বোর্ড অনেক তথ্য " * 220
        + "\\nজনাব কল্পিত পরীক্ষা\\nমাননীয় প্রধানমন্ত্রী\\nগণপ্রজাতন্ত্রী বাংলাদেশ সরকার"
    )

    def transport(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"results": [{
            "url": "https://pmo.gov.bd/",
            "raw_content": long_page,
        }]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = research_web(
            officeholder_search_query("tell me bd pm name"),
            include_domains=["pmo.gov.bd", "cabinet.gov.bd"],
            max_sources=2,
            client=client,
        )
    assert result.provider_name == "aqlyra-official-fact"
    assert "কল্পিত পরীক্ষা" in result.answer
    assert len(result.sources[0].excerpt) <= 3_000
