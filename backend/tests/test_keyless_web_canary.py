"""SearXNG E2E public canary is bounded and never logs private content."""
from types import SimpleNamespace

from app.config.settings import settings
from app.services import keyless_web_canary as canary
from app.services.web_research_service import WebResearchEvidenceError


def test_disabled_keyless_canary_does_not_call_remote(monkeypatch):
    monkeypatch.setattr(settings, "WEB_KEYLESS_CANARY_ON_STARTUP", False)
    monkeypatch.setattr(
        canary, "_research_web_searxng",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("A default-off canary must not call network")
        ),
    )
    assert canary.run_keyless_web_canary() is False


def test_keyless_canary_success_emits_counts_not_question_or_answer(monkeypatch, caplog):
    monkeypatch.setattr(settings, "WEB_KEYLESS_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(
        canary, "configured_searxng_url",
        lambda: "https://trusted-gateway.onrender.com",
    )
    calls = []
    def fake_research(question, *, max_sources, mode):
        calls.append((question, max_sources, mode))
        return SimpleNamespace(
            answer="Factual public answer [W1].",
            sources=[SimpleNamespace(url="https://en.wikipedia.org/wiki/Bangladesh")],
        )
    monkeypatch.setattr(canary, "_research_web_searxng", fake_research)
    with caplog.at_level("INFO"):
        assert canary.run_keyless_web_canary() is True
    assert len(calls) == 1 and calls[0][1:] == (4, "search")
    assert "status=PASS source_count=1" in caplog.text
    assert "Factual public answer" not in caplog.text
    assert canary._PUBLIC_QUESTION not in caplog.text


def test_keyless_failure_does_not_log_source_text(monkeypatch, caplog):
    monkeypatch.setattr(settings, "WEB_KEYLESS_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    monkeypatch.setattr(canary, "configured_searxng_url", lambda: "https://example.org")
    def fail(*args, **kwargs):
        raise WebResearchEvidenceError("PRIVATE TEST PAGE BODY")
    monkeypatch.setattr(canary, "_research_web_searxng", fail)
    with caplog.at_level("WARNING"):
        assert canary.run_keyless_web_canary() is False
    assert "PRIVATE TEST PAGE BODY" not in caplog.text
    assert "WebResearchEvidenceError" in caplog.text
