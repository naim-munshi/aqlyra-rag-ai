"""Production-screenshot regression using current-style first-party roster pages.

All persons in fixtures are synthetic. No live accounts, paid Tavily/Groq,
secrets or production documents are accessed by this test.
"""
import json

import httpx
import pytest

from app.config.settings import settings
from app.services.public_office_guard import (
    officeholder_additional_authoritative_urls,
    officeholder_source_query,
    officeholder_search_query,
)
from app.services.web_research_service import research_web
from app.services.official_fact_fast_path import _extract_current_bd_name


DIRECTORY = officeholder_additional_authoritative_urls(
    "tell me bd pm name"
)[0]
NAME = "কল্পিত পরীক্ষা"
PUBLIC_DIRECTORY_TEXT = (
    "নোটিশ প্রকাশনা কনটেন্ট মন্ত্রণালয় " * 210
    + "\n## প্রধানমন্ত্রী ও মন্ত্রিগণ\n"
    + "ক্রম | ছবি | নাম | পদবি | নিয়োগের তারিখ\n"
    + "১ | Image | জনাব " + NAME
    + " | প্রধানমন্ত্রী | ১৭-০২-২০২৬\n"
    + "নিয়োগের তারিখ: ১৭-০২-২০২৬\n"
)
PMO_NAVIGATION = "দপ্তর মেনু ও নোটিশ " * 280


@pytest.fixture
def mocked_official_search(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    requests = []

    def handle(request: httpx.Request):
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path == "/search":
            # Recreate screenshot's problem: generic search only finds the
            # two government homepages, no current-officeholder detail.
            assert "include_domains" in body
            assert "মন্ত্রিপরিষদ" in body["query"]
            return httpx.Response(200, json={"results": [
                {
                    "url": "https://pmo.gov.bd/",
                    "title": "Prime Minister's Office",
                    "content": "Navigation, forms, office news",
                },
                {
                    "url": "https://cabinet.gov.bd/",
                    "title": "Cabinet Division",
                    "content": "Government contacts, menus",
                },
            ]})
        assert request.url.path == "/extract"
        assert "https://pmo.gov.bd/" in body["urls"]
        assert DIRECTORY in body["urls"]
        return httpx.Response(200, json={"results": [
            {"url": "https://pmo.gov.bd/", "raw_content": PMO_NAVIGATION},
            {"url": DIRECTORY, "raw_content": PUBLIC_DIRECTORY_TEXT},
        ]})

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def test_name_only_returns_identity_with_usable_citation_not_homepage_refusal(
    mocked_official_search,
    monkeypatch,
):
    client, recorded = mocked_official_search
    with client:
        result = research_web(
            officeholder_search_query("tell me bd pm name"),
            include_domains=["pmo.gov.bd", "cabinet.gov.bd"],
            max_sources=2,
            client=client,
        )
    assert result.provider_name == "aqlyra-official-fact"
    assert NAME in result.answer
    assert "can't confirm" not in result.answer.lower()
    assert result.answer.endswith("[W1]")
    assert len(result.sources) == 1
    assert result.sources[0].url == DIRECTORY
    assert result.sources[0].citation == "[W1]"
    assert [path for path, _ in recorded] == ["/search", "/extract"]


def test_profile_short_answer_includes_government_appointment_without_groq(
    mocked_official_search,
    monkeypatch,
):
    client, recorded = mocked_official_search
    with client:
        result = research_web(
            officeholder_search_query("tell me about bd pm"),
            include_domains=["pmo.gov.bd", "cabinet.gov.bd"],
            max_sources=3,
            client=client,
        )
    assert result.provider_name == "aqlyra-official-fact"
    assert NAME in result.answer
    assert "17 February 2026" in result.answer
    assert "current Prime Minister" in result.answer
    assert result.answer.endswith("[W1]")
    assert result.sources[0].url == DIRECTORY
    assert len(recorded) == 2


def test_live_style_table_parser_handles_rows_and_collapsed_cabinet_text():
    assert _extract_current_bd_name(PUBLIC_DIRECTORY_TEXT) == NAME
    # Government HTML-to-text sometimes collapses a table cell:
    assert _extract_current_bd_name(
        "| প্রধানমন্ত্রীজনাব " + NAME + " | মন্ত্রিপরিষদ বিভাগ\n"
    ) == NAME


def test_search_query_is_short_relevant_and_does_not_send_private_history():
    query = officeholder_source_query(
        officeholder_search_query("tell me about bd pm")
    )
    assert "মন্ত্রিপরিষদ বিভাগ" in query
    assert "cabinet.gov.bd" in query
    assert len(query) < 200


def test_evergreen_questions_keep_original_search_query():
    query = "What is an operating system?"
    assert officeholder_source_query(query) == query
