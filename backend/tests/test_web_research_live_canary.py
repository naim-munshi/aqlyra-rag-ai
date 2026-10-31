"""No-secret opt-in Web Research canary contract."""
from types import SimpleNamespace

import app.services.web_research_live_canary as canary
from app.config.settings import settings
from app.services.web_research_service import WebResearchEvidenceError


def test_web_canary_off_is_free_and_no_network(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_CANARY_ON_STARTUP", False)
    monkeypatch.setattr(
        canary, "research_web",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No request")),
    )
    assert canary.run_live_web_canary() is False


def test_web_canary_checks_full_pipeline_without_outputting_answer(monkeypatch, caplog):
    monkeypatch.setattr(settings, "WEB_RESEARCH_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)
    queries = []

    def fake_research(query, **kwargs):
        queries.append((query, kwargs))
        return SimpleNamespace(
            answer="A result with a valid citation [W1].",
            sources=[SimpleNamespace(citation="[W1]")],
        )

    monkeypatch.setattr(canary, "research_web", fake_research)
    with caplog.at_level("INFO"):
        assert canary.run_live_web_canary() is True
    assert len(queries) == 1
    assert queries[0][1]["max_sources"] == 4
    assert "status=PASS" in caplog.text
    assert "A result with a valid citation" not in caplog.text


def test_web_canary_logs_failure_class_not_source_or_key(monkeypatch, caplog):
    monkeypatch.setattr(settings, "WEB_RESEARCH_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", True)

    def failed(*args, **kwargs):
        raise WebResearchEvidenceError("Do not leak sensitive query or API key")
    monkeypatch.setattr(canary, "research_web", failed)
    with caplog.at_level("WARNING"):
        assert canary.run_live_web_canary() is False
    assert "WebResearchEvidenceError" in caplog.text
    assert "sensitive query" not in caplog.text
    assert "API key" not in caplog.text


def test_web_canary_is_skipped_if_provider_disabled(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    assert canary.run_live_web_canary() is False
