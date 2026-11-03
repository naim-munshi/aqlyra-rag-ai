"""Official-evidence relevance and time filter end-to-end mock transport.

No live network, credentials, person names or production data.
"""
import json

import httpx

from app.config.settings import settings
from app.llms.types import LLMGeneration
from app.services.public_office_guard import officeholder_search_query
from app.services.web_research_service import research_web


class EvidenceOnlyProvider:
    def __init__(self):
        self.received = None

    def generate(self, *, instructions, input_text):
        self.received = json.loads(input_text)
        return LLMGeneration(
            text="The official administration lists the verified incumbent [W1].",
            provider_name="synthetic",
            model_name="synthetic",
        )


def test_off_topic_web_pages_are_excluded_before_grounding(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "synthetic-test-only")
    observed = []
    def provider(request: httpx.Request):
        assert request.url.host == "api.tavily.com"
        payload = json.loads(request.content)
        observed.append((request.url.path, payload))
        if request.url.path == "/search":
            assert payload.get("time_range") is None
            assert payload.get("include_domains") == ["whitehouse.gov"]
            return httpx.Response(200, json={"results": [
                {
                    "url": "https://unrelated.example.org/election-voting-guide",
                    "title": "Unrelated election guide",
                    "raw_content": "This is not about the incumbent",
                },
                {
                    "url": "https://www.whitehouse.gov/administration/",
                    "title": "Official Administration",
                    "raw_content": "Administration of the current United States president",
                },
            ]})
        if request.url.path == "/extract":
            # A first-party page must be freshly extracted even if a
            # cached search response already had raw_content.
            assert payload["urls"] == ["https://www.whitehouse.gov/administration/"]
            return httpx.Response(200, json={"results": [{
                "url": "https://www.whitehouse.gov/administration/",
                "raw_content": "Administration of the current United States president",
            }]})
        raise AssertionError("Unexpected endpoint")

    model = EvidenceOnlyProvider()
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        result = research_web(
            officeholder_search_query("Who is the current US president?"),
            max_sources=5,
            time_range=None,
            include_domains=["whitehouse.gov"],
            client=client,
            provider=model,
        )
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://www.whitehouse.gov/administration/"
    assert "unrelated" not in json.dumps(model.received)
    assert "[W1]" in result.answer
    assert observed[0][0] == "/search"
