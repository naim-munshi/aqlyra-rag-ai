"""Regression for the actual 'tell me about bd pm' production failure.

All officeholder names are fictional. No real user data, provider credits or
network calls are made. Retrieval must surface verifiable *current* government
evidence, not generate long self-referential refusals because one homepage
has only a menu.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.config.settings import settings
from app.llms.types import LLMGeneration
from app.services import chat_service, smart_web_router
from app.services.auto_web_research_service import cited_web_answer
from app.services.official_fact_fast_path import verified_officeholder_fast_answer
from app.services.public_office_guard import (
    is_bangladesh_pm_profile_question,
    is_public_officeholder_question,
    officeholder_primary_domains,
    officeholder_search_query,
)
from app.services.web_research_service import research_web
from app.schemas.web_research import WebResearchSource


CABINET_DETAIL = (
    "https://cabinet.gov.bd/pages/office-heads/"
    "current-prime-minister"
)
SYNTHETIC_NAME = "কল্পিত পরীক্ষা"
OFFICIAL_PAGE = (
    "নোটিশ ও সরকারি পত্র " * 230
    + "\n### প্রধানমন্ত্রী\nImage\nজনাব "
    + SYNTHETIC_NAME
    + "\nপ্রধানমন্ত্রী\nনিয়োগের তারিখ: ১৭-০২-২০২৬"
)


@pytest.mark.parametrize("question", [
    "tell me about bd pm",
    "tell me about Bangladesh prime minister",
    "give me information about bd pm",
])
def test_real_world_short_public_profile_uses_search_not_llm_selector(monkeypatch, question):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "mock-key")
    assert is_bangladesh_pm_profile_question(question)
    assert not is_public_officeholder_question(question)
    assert smart_web_router.route_web_request(question, mode="auto") == "search"
    assert officeholder_primary_domains(question) == [
        "pmo.gov.bd", "cabinet.gov.bd",
    ]
    query = officeholder_search_query(question)
    assert query.startswith("Who is the current prime minister of Bangladesh?")
    assert "brief" in query
    assert "background" in query


def test_profile_and_identity_are_distinct_lanes(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "mock-key")
    seen = []

    def fake_research(query, **kwargs):
        seen.append((query, kwargs))
        return SimpleNamespace(
            answer="The incumbent has a verified current government profile [W1].",
            sources=[
                SimpleNamespace(
                    title="Official Cabinet",
                    url=CABINET_DETAIL,
                    citation="[W1]",
                )
            ],
            provider_name="synthetic-research",
            model_name="test",
        )

    monkeypatch.setattr(chat_service, "research_web", fake_research)
    result = chat_service.generate_web_chat_reply(
        message="tell me about bd pm",
        research_mode="search",
    )
    assert seen[0][1]["include_domains"] == [
        "pmo.gov.bd", "cabinet.gov.bd",
    ]
    assert seen[0][1]["max_sources"] == 3
    assert "brief" in seen[0][0]
    assert "cabinet.gov.bd" in result.content


def _transport(request: httpx.Request):
    payload = json.loads(request.content)
    if request.url.path == "/search":
        assert payload["include_domains"] == [
            "pmo.gov.bd", "cabinet.gov.bd",
        ]
        return httpx.Response(200, json={"results": [
            {"url": CABINET_DETAIL, "title": "Current Prime Minister",
             "content": "public current cabinet listing"},
        ]})
    assert request.url.path == "/extract"
    assert payload["urls"] == ["https://pmo.gov.bd/", CABINET_DETAIL]
    return httpx.Response(200, json={"results": [
        {"url": "https://pmo.gov.bd/", "raw_content": "# PMO\nNotices and services only"},
        {"url": CABINET_DETAIL, "raw_content": OFFICIAL_PAGE},
    ]})


@pytest.fixture
def official_search(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-only")
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    return httpx.Client(transport=httpx.MockTransport(_transport))


def test_name_only_when_pmo_has_no_name_uses_second_official_page(official_search):
    with official_search as client:
        result = research_web(
            officeholder_search_query("tell me bd pm name"),
            include_domains=["pmo.gov.bd", "cabinet.gov.bd"],
            max_sources=2,
            client=client,
        )
    assert result.provider_name == "aqlyra-official-fact"
    assert SYNTHETIC_NAME in result.answer
    assert result.answer.endswith("[W1]")
    assert len(result.sources) == 1
    assert result.sources[0].citation == "[W1]"
    assert result.sources[0].url == CABINET_DETAIL
    assert "cabinet.gov.bd" in cited_web_answer(result.answer, result.sources)


class ProfileProvider:
    def __init__(self):
        self.body = None
    def generate(self, *, instructions, input_text):
        self.body = json.loads(input_text)
        assert "UNTRUSTED" in instructions
        return LLMGeneration(
            text="The incumbent was appointed by the government [W2].",
            provider_name="synthetic-llm",
            model_name="mock",
        )


def test_about_question_extracts_relevant_official_evidence_not_first_3000_chars(
    official_search,
):
    provider = ProfileProvider()
    with official_search as client:
        result = research_web(
            officeholder_search_query("tell me about bd pm"),
            include_domains=["pmo.gov.bd", "cabinet.gov.bd"],
            max_sources=3,
            provider=provider,
            client=client,
        )
    assert result.provider_name == "synthetic-llm"
    relevant = [
        s for s in provider.body["retrieved_public_evidence"]
        if s["url"] == CABINET_DETAIL
    ]
    assert len(relevant) == 1
    assert SYNTHETIC_NAME in relevant[0]["excerpt"]
    assert "প্রধানমন্ত্রী" in relevant[0]["excerpt"]
    assert len(relevant[0]["excerpt"]) <= 3000
    assert result.answer.endswith("[W2].")


def test_unspecified_historical_office_not_forced_into_current_fast_path():
    assert not is_bangladesh_pm_profile_question(
        "tell me about bd pm in 2010"
    )


def test_stale_only_or_fake_domains_cannot_be_fast_evidence():
    fake = WebResearchSource(
        citation="[W1]", title="Unrelated archive",
        url="https://untrusted.example.org/profile",
        excerpt="জনাব " + SYNTHETIC_NAME + "\nপ্রধানমন্ত্রী",
        published_date=None,
    )
    assert verified_officeholder_fast_answer(
        "Who is the prime minister of Bangladesh?",
        [fake],
        extracted_urls={fake.url},
    ) is None
