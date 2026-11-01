"""Deterministic navigation quality, resilience and security tests.

Never uses actual internet, browser, model credentials, or production records.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app.services import browser_agent_service as agent
from app.services import browser_public_html_service as public

HOST = "docs.example.org"
START = "https://docs.example.org/start"


def test_canonical_url_removes_only_tracking_and_fragments():
    url = "https://docs.example.org/guide?utm_source=news&q=rag&page=2&fbclid=x#overview"
    assert agent._canonical_public_url(url, HOST) == (
        "https://docs.example.org/guide?q=rag&page=2"
    )
    assert agent._canonical_public_url("https://docs.example.org", HOST) == (
        "https://docs.example.org/"
    )
    assert agent._canonical_public_url("https://docs.example.org/logout#x", HOST) is None
    assert agent._canonical_public_url("https://evil.example.com/guide", HOST) is None
    assert agent._canonical_public_url(
        "https://docs.example.org/docs?next=%252flogout", HOST
    ) is None


def test_frontier_deduplicates_variants_without_dropping_real_search_parameters():
    front = agent._merge_link_frontier([], [
        {"href": "/guide?utm_source=a#top", "text": "Guide 1"},
        {"href": "/guide?utm_source=b#bottom", "text": "Guide 2"},
        {"href": "/guide?q=security", "text": "Security"},
        {"href": "/guide?q=pricing", "text": "Pricing"},
        {"href": "/logout", "text": "Unsafe"},
        {"href": "https://evil.example.com/", "text": "External"},
    ], START, HOST, {START})
    assert [link["url"] for link in front] == [
        "https://docs.example.org/guide",
        "https://docs.example.org/guide?q=security",
        "https://docs.example.org/guide?q=pricing",
    ]


def test_task_ranker_surfaces_relevant_link_outside_first_25_candidates():
    raw = [
        {"href": f"/misc/{i}", "text": f"General navigation {i}"}
        for i in range(38)
    ]
    raw.append({
        "href": "/releases/security-2026",
        "text": "Security release notes for 2026",
    })
    front = agent._merge_link_frontier([], raw, START, HOST, {START})
    assert front.index(next(x for x in front if "security-2026" in x["url"])) >= 25
    ranked = agent._rank_link_frontier(front, "Find 2026 security release notes")
    assert ranked[0]["url"] == "https://docs.example.org/releases/security-2026"
    assert len(front) <= agent.MAX_LINK_FRONTIER
    assert front == agent._rank_link_frontier(front, "the and for how")


def test_secondary_broken_page_is_skipped_and_previous_citations_survive(monkeypatch):
    failed = "https://docs.example.org/releases/security"
    good = "https://docs.example.org/releases/guide"
    requested = []

    async def dns(_host):
        return "93.184.216.34"

    def read(url, host, ip):
        assert host == HOST and ip == "93.184.216.34"
        requested.append(url)
        if url == failed:
            raise agent.BrowserAgentPlanError("404")
        if url == START:
            return {
                "url": url, "title": "Start", "text": "Documented release overview",
                "links": [
                    {"href": "/releases/security", "text": "Security release"},
                    {"href": "/releases/guide", "text": "Guide"},
                ],
            }
        return {
            "url": url, "title": "Guide", "text": "Detailed source evidence",
            "links": [],
        }

    monkeypatch.setattr(agent, "_validate_public_dns", dns)
    monkeypatch.setattr(public, "_read_public_snapshot", read)

    class Llm:
        def generate(self, *, instructions, input_text):
            if "available_same_site_links" in input_text:
                data = json.loads(input_text)
                assert data["available_same_site_links"][0]["url_path"] == "/releases/security"
                return SimpleNamespace(
                    text='{"action":"follow","link_number":1}', model_name="test"
                )
            data = json.loads(input_text)
            assert data["navigation_notes"]["failed_link_attempts"] == 1
            return SimpleNamespace(text="The guide exists [B1] [B2].", model_name="test")

    result = asyncio.run(public.run_read_only_html_browser(
        "Find security release guide", START, HOST, Llm(),
    ))
    assert requested == [START, failed, good]
    assert len(result.visited) == 2
    assert result.visited[0].citation == "[B1]"
    assert result.visited[1].citation == "[B2]"
    assert any("unavailable" in step for step in result.steps)


def test_failed_start_page_is_not_misreported_as_research(monkeypatch):
    async def dns(_host):
        return "93.184.216.34"
    monkeypatch.setattr(agent, "_validate_public_dns", dns)

    def unavailable(*_):
        raise agent.BrowserAgentPlanError("Blocked")
    monkeypatch.setattr(public, "_read_public_snapshot", unavailable)
    with pytest.raises(agent.BrowserAgentPlanError, match="Blocked"):
        asyncio.run(public.run_read_only_html_browser(
            "Read public docs", START, HOST, object(),
        ))


def test_link_failures_have_hard_bounded_retry_budget(monkeypatch):
    seen = []

    async def dns(_host):
        return "93.184.216.34"

    def reader(url, *_):
        seen.append(url)
        if url != START:
            raise agent.BrowserAgentPlanError("Missing")
        return {
            "url": url, "title": "Overview", "text": "Official source",
            "links": [{"href": f"/bad-{i}", "text": f"Bad {i}"} for i in range(15)],
        }

    monkeypatch.setattr(agent, "_validate_public_dns", dns)
    monkeypatch.setattr(public, "_read_public_snapshot", reader)

    class Llm:
        def generate(self, *, instructions, input_text):
            if "available_same_site_links" in input_text:
                return SimpleNamespace(
                    text='{"action":"follow","link_number":1}', model_name="test"
                )
            return SimpleNamespace(text="Only overview is available [B1].", model_name="test")

    result = asyncio.run(public.run_read_only_html_browser(
        "Find product release details", START, HOST, Llm(),
    ))
    assert len(seen) == agent.MAX_PAGES + 2
    assert len(set(seen)) == len(seen)
    assert len(result.visited) == 1
    assert result.answer.endswith("[B1].")


def test_article_extraction_prioritizes_content_and_excludes_navigation(monkeypatch):
    class Page:
        status = 200
        headers = {"Content-Type": "text/html"}
        def read(self, amount, decode_content):
            return b"""<html><head><title>Knowledge Base</title></head>
              <body><header>Unrelated header navigation</header>
              <nav>Account Settings Dashboard</nav>
              <main><article><h1>Detailed technical content</h1>
              <p>This guide documents the real deployment procedure step by step.</p>
              </article></main>
              <footer>Unrelated site-wide links</footer></body></html>"""
        def close(self): pass
    class Pool:
        def __init__(self, *_args, **_kwargs): pass
        def urlopen(self, *_args, **_kwargs): return Page()
        def close(self): pass
    monkeypatch.setattr(public, "HTTPSConnectionPool", Pool)
    result = public._read_public_snapshot(START, HOST, "93.184.216.34")
    assert "Detailed technical content" in result["text"]
    assert "Unrelated header" not in result["text"]
    assert "Account Settings Dashboard" not in result["text"]
    assert result["title"] == "Knowledge Base"
