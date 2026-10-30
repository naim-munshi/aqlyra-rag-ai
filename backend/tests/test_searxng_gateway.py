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
