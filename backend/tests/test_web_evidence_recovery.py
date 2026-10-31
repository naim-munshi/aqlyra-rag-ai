"""Regression tests for bounded Tavily source recovery and citation repair."""
import json

import httpx
import pytest

from app.config.settings import settings
from app.llms.types import LLMGeneration
from app.services.web_research_service import (
    WebResearchEvidenceError,
    research_web,
)


class SequencedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def generate(self, *, instructions, input_text):
        self.calls += 1
        assert "UNTRUSTED" in instructions
        evidence = json.loads(input_text)["retrieved_public_evidence"]
        assert evidence
        return LLMGeneration(
            text=self.replies[min(self.calls - 1, len(self.replies) - 1)],
            provider_name="test",
            model_name="test",
        )


def _run(monkeypatch, handler, replies):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "fake-key")
    model = SequencedLLM(replies)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = research_web(
            "What do verified sources establish?",
            client=client,
            provider=model,
        )
    return result, model


def test_search_raw_content_survives_extract_empty(monkeypatch):
    def handler(req):
        if req.url.path == "/search":
            assert json.loads(req.content)["include_raw_content"] is True
            return httpx.Response(200, json={"results": [{
                "url": "https://example.org/official",
                "title": "Official evidence",
                "raw_content": "Verified document from the search provider.",
                "content": "Short snippet that is not sufficient evidence.",
            }]})
        return httpx.Response(200, json={"results": [], "failed_results": []})

    result, model = _run(monkeypatch, handler, ["The official evidence states this [W1]."])
    assert model.calls == 1
    assert len(result.sources) == 1
    assert "Verified document" in result.sources[0].excerpt
    assert "Short snippet" not in result.sources[0].excerpt


def test_search_raw_content_survives_extract_error(monkeypatch):
    def handler(req):
        if req.url.path == "/search":
            return httpx.Response(200, json={"results": [{
                "url": "https://example.org/official",
                "raw_content": "Page text from the search provider.",
            }]})
        return httpx.Response(503, json={"error": "Temporarily unavailable"})

    result, _ = _run(monkeypatch, handler, ["Grounded page evidence [W1]."])
    assert len(result.sources) == 1


def test_repairs_missing_citation_with_same_evidence(monkeypatch):
    def handler(req):
        if req.url.path == "/search":
            return httpx.Response(200, json={"results": [{
                "url": "https://example.org/official",
                "title": "Official",
            }]})
        return httpx.Response(200, json={"results": [{
            "url": "https://example.org/official",
            "raw_content": "The official facts.",
        }]})

    result, model = _run(monkeypatch, handler, [
        "Unsourced output.",
        "The official facts are provided by the source [W1].",
    ])
    assert model.calls == 2
    assert result.answer.endswith("[W1].")


def test_still_refuses_fabricated_links_and_citations(monkeypatch):
    def handler(req):
        if req.url.path == "/search":
            return httpx.Response(200, json={"results": [{
                "url": "https://example.org/official",
                "raw_content": "Official source evidence",
            }]})
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "fake-key")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        model = SequencedLLM(["A false citation [W42]."] * 2)
        with pytest.raises(WebResearchEvidenceError):
            research_web("What do verified sources establish?", client=client, provider=model)
        assert model.calls == 2

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        model = SequencedLLM([
            "Fake link https://evil.org/path [W1].",
            "Still fake https://evil.org/path [W1].",
        ])
        with pytest.raises(WebResearchEvidenceError):
            research_web("What do verified sources establish?", client=client, provider=model)
        assert model.calls == 2
