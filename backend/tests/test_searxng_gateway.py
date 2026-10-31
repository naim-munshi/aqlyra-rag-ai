"""Validate the public SearXNG gateway allows only token-gated JSON search."""
import importlib.util
from pathlib import Path

import pytest


def load_gateway():
    root = Path(__file__).resolve().parents[2]
    path = root / "ops" / "searxng" / "gateway.py"
    spec = importlib.util.spec_from_file_location("aqlyra_searxng_gateway", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("url", [
    "/search?q=Bangladesh+prime+minister&format=json&pageno=1&safesearch=1",
    "/search?q=latest+jobs&format=json",
    "/search?q=AI+research&format=json&time_range=month",
])
def test_bounded_json_search_allowed(url):
    gateway = load_gateway()
    target = gateway.validated_search_path(url)
    assert target is not None
    assert target.startswith("/search?q=")
    assert "format=json" in target


@pytest.mark.parametrize("url", [
    "/",
    "/admin",
    "/search",
    "/search?q=hello&format=html",
    "/search?q=hello&format=json&format=json",
    "/search?q=x&format=json",
    "/search?q=hello&format=json&url=http://169.254.169.254",
    "/search?q=hello&format=json&pageno=2",
    "/search?q=hello&format=json&safesearch=0",
    "/search?q=hello&format=json&time_range=all",
    "/search?q=hello&format=json&x=1",
    "//private.internal/search?q=hello&format=json",
    "/search?q=hello%0d%0aInjected&format=json",
])
def test_gateway_does_not_provide_open_proxy(url):
    gateway = load_gateway()
    assert gateway.validated_search_path(url) is None


def test_wikipedia_fallback_only_uses_verified_page_ids(monkeypatch):
    gateway = load_gateway()

    class FakeResponse:
        status = 200
        def getheader(self, key, default=""):
            return "application/json" if key == "Content-Type" else default
        def read(self, length):
            return (
                b'{"query":{"search":[{"pageid":123,"title":"Bangladesh",'
                b'"snippet":"Country in <span>South Asia</span>"},'
                b'{"pageid":-1,"title":"Invalid","snippet":"bad"},'
                b'{"title":"No identifier","snippet":"bad"}]}}'
            )

    class FakeConnection:
        def __init__(self, hostname, port, timeout):
            assert hostname == "en.wikipedia.org"
            assert port == 443 and timeout <= 3
        def request(self, method, path, headers):
            assert method == "GET"
            assert path.startswith("/w/api.php?")
            assert "Bangladesh" in path
            assert not any("Authorization" in k for k in headers)
        def getresponse(self):
            return FakeResponse()
        def close(self):
            pass

    monkeypatch.setattr(gateway.http.client, "HTTPSConnection", FakeConnection)
    hits = gateway.wikipedia_public_search("Bangladesh")
    assert len(hits) == 1
    assert hits[0]["url"] == "https://en.wikipedia.org/?curid=123"
    assert "<span>" not in hits[0]["content"]
    assert hits[0]["engine"] == "wikipedia-api"


def test_wikipedia_fallback_never_issues_arbitrary_search_endpoint(monkeypatch):
    gateway = load_gateway()
    calls = []
    class FakeConnection:
        def __init__(self, *args, **kwargs):
            calls.append("connected")
            raise OSError("network unavailable")
    monkeypatch.setattr(gateway.http.client, "HTTPSConnection", FakeConnection)
    assert gateway.wikipedia_public_search("Japan") == []
    assert calls == ["connected"]
    assert gateway.wikipedia_public_search("x") == []
    assert calls == ["connected"]
