"""Live Web Search config diagnostics never disclose credentials or imply E2E PASS."""
import pytest

from app.config.settings import settings
from app.services.public_office_guard import unverified_officeholder_reply
from app.services.web_research_capability import public_web_research_status


@pytest.mark.parametrize(
    ("enabled", "key", "expected"),
    [
        (False, "", "disabled_and_missing_key"),
        (False, "dummy-secret-not-for-production", "disabled_key_present"),
        (True, "", "missing_tavily_api_key"),
        (True, "dummy-secret-not-for-production", "configured_unverified"),
    ],
)
def test_web_config_status_not_a_provider_health_claim(monkeypatch, enabled, key, expected):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", enabled)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", key)
    status = public_web_research_status()
    assert status == expected
    assert "dummy-secret" not in status
    assert "verified" not in status or status == "configured_unverified"


@pytest.mark.parametrize(
    ("enabled", "key", "needle"),
    [
        (False, "", "Tavily"),
        (False, "test-only", "administrator"),
        (True, "", "Tavily"),
        (True, "test-only", "Web Search"),
    ],
)
def test_english_officeholder_refusal_reports_correct_configuration(
    monkeypatch, enabled, key, needle,
):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", enabled)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", key)
    answer = unverified_officeholder_reply(
        "Who is the current prime minister of Bangladesh?"
    )
    assert answer is not None
    assert "can't verify" in answer
    assert needle.lower() in answer.lower()
    assert "test-only" not in answer


def test_no_provider_diagnostics_for_ambiguous_question(monkeypatch):
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    assert unverified_officeholder_reply("prime minister nam") == (
        "Which country do you mean?"
    )


def test_readiness_reports_public_web_capability_without_secret(
    client, monkeypatch,
):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "sensitive-example-do-not-log")
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["checks"]["public_web_research"] == "disabled_key_present"
    assert "sensitive-example" not in response.text
