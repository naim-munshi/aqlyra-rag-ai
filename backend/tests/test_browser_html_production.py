"""Public HTML-only browser does not navigate inside private networks or execute JS."""
import asyncio
from types import SimpleNamespace

import pytest

from app.config.settings import settings
from app.services import browser_agent_service as browser
from app.services import browser_public_html_service as html_browser


def test_html_reader_pins_tls_and_filters_cross_site_links(monkeypatch):
    calls = {}
    class FakePage:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def read(self, n, decode_content):
            assert n == html_browser.MAX_BYTES + 1
            return b"""<html><head><title>Official API docs</title></head>
            <body><h1>Release notes and public API documentation</h1>
            <a href="/guide">Guide</a><a href="https://127.0.0.1/private">Unsafe</a>
            <a href="/logout">Delete session</a>
            <script>fetch('http://localhost/secrets')</script>
            </body></html>"""
        def close(self):
            pass
    class FakePool:
        def __init__(self, ip, **kwargs):
            calls.update({"ip": ip, **kwargs})
        def urlopen(self, method, path, **kwargs):
            calls["request"]=(method,path,kwargs)
            return FakePage()
        def close(self):
            pass
    monkeypatch.setattr(html_browser, "HTTPSConnectionPool", FakePool)
    page=html_browser._read_public_snapshot(
        "https://docs.example.org/release", "docs.example.org", "93.184.216.34",
    )
    assert calls["ip"]=="93.184.216.34"
    assert calls["assert_hostname"]=="docs.example.org"
    assert calls["server_hostname"]=="docs.example.org"
    assert calls["request"][2]["redirect"] is False
    assert "localhost" not in page["text"]
    assert [x["href"] for x in page["links"]]==["https://docs.example.org/guide"]


def test_html_browser_uses_only_approved_pages_and_citations(monkeypatch):
    start="https://docs.example.org/release"
    second="https://docs.example.org/guide"
    async def pinned(host):
        assert host=="docs.example.org"
        return "93.184.216.34"
    monkeypatch.setattr(browser,"_validate_public_dns",pinned)
    seen=[]
    def fake_reader(url, host, ip):
        seen.append(url)
        assert host=="docs.example.org" and ip=="93.184.216.34"
        return {
            "url":url, "title":"Docs", "text":"Official release guide explains the API.",
            "links":[{"href":"/guide","text":"Guide"},{"href":"http://127.0.0.1","text":"Evil"}]
            if url==start else [],
        }
    monkeypatch.setattr(html_browser,"_read_public_snapshot",fake_reader)
    class FakeLLM:
        count=0
        def generate(self, *, instructions, input_text):
            self.count+=1
            if self.count==1:
                return SimpleNamespace(text='{"action":"follow","link_number":1}',model_name="mock")
            return SimpleNamespace(text="The docs support this [B1] [B2].",model_name="mock")
    result=asyncio.run(html_browser.run_read_only_html_browser(
        "Read official API documentation",start,"docs.example.org",FakeLLM(),
    ))
    assert seen==[start,second]
    assert result.answer.endswith("[B2].")
    assert len(result.visited)==2
    assert [e.url for e in result.visited]==[start,second]


def test_html_browser_rejects_fake_llm_citations(monkeypatch):
    async def pinned(host):
        return "93.184.216.34"
    monkeypatch.setattr(browser,"_validate_public_dns",pinned)
    monkeypatch.setattr(html_browser,"_read_public_snapshot",lambda url,host,ip:{
        "url":url,"title":"Docs","text":"Some public contents here.",
        "links":[],
    })
    model=SimpleNamespace(generate=lambda **kw: SimpleNamespace(
        text="Unsupported citation [B88].",model_name="mock",
    ))
    with pytest.raises(browser.BrowserAgentPlanError,match="citations"):
        asyncio.run(html_browser.run_read_only_html_browser(
            "Read public docs","https://docs.example.org/guide","docs.example.org",model,
        ))


def test_production_html_browser_requires_both_gates(monkeypatch):
    monkeypatch.setattr(settings,"APP_ENV","production")
    monkeypatch.setattr(settings,"BROWSER_AGENT_ENABLED",True)
    monkeypatch.setattr(settings,"BROWSER_AGENT_ALLOWED_HOSTS","docs.example.org")
    monkeypatch.setattr(settings,"LLM_PROVIDER","groq")
    monkeypatch.setattr(settings,"BROWSER_APPROVAL_REDIS_ENABLED",False)
    monkeypatch.setattr(settings,"BROWSER_AGENT_HTML_ONLY_PRODUCTION_ENABLED",True)
    monkeypatch.setattr(settings,"REDIS_URL","rediss://example.invalid:6379")
    with pytest.raises(browser.BrowserAgentUnavailable):
        browser._check_feature()
    monkeypatch.setattr(settings,"BROWSER_APPROVAL_REDIS_ENABLED",True)
    assert browser._check_feature() is None
