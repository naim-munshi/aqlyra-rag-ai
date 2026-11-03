"""Live-screenshot source-quality regression; no network or paid model calls."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import chat_service
from app.services.public_office_guard import (
    officeholder_primary_domains,
    officeholder_search_query,
)


@pytest.mark.parametrize("question", [
    "Who is the current US president?",
    "What is the name of us presodent",
    "What is the name of the US president?",
    "Who is the president of the United States?",
    "Who is the current president of America?",
])
def test_current_us_office_requires_first_party_government_source(question):
    assert officeholder_primary_domains(question) == ["whitehouse.gov"]
    canonical = officeholder_search_query(question)
    assert "White House administration" in canonical
    assert "official government source" in canonical
    assert "presodent" not in canonical


@pytest.mark.parametrize("question", [
    "How do presidential elections work?",
    "Who was the US president in 2010?",
    "Who is the prime minister of Japan?",
    "Can you find my salary details?",
])
def test_unrelated_or_historical_question_has_no_us_domain_lock(question):
    assert officeholder_primary_domains(question) is None


def test_current_officeholder_web_search_omits_month_filter_and_other_domains(
    monkeypatch,
):
    captured = []

    def mock_research(question, **options):
        captured.append({"question": question, **options})
        return SimpleNamespace(
            answer="Verified officeholder from the official administration [W1].",
            sources=[
                SimpleNamespace(
                    citation="[W1]",
                    title="Official White House Administration",
                    url="https://www.whitehouse.gov/administration/",
                )
            ],
            provider_name="synthetic-web",
            model_name="stub",
        )

    monkeypatch.setattr(chat_service, "research_web", mock_research)
    result = chat_service.generate_web_chat_reply(
        message="Who is the current US president?",
        research_mode="search",
    )

    assert len(captured) == 1
    assert captured[0]["include_domains"] == ["whitehouse.gov"]
    assert captured[0]["time_range"] is None
    assert "official government source" in captured[0]["question"]
    assert "[W1]" in result.content
    assert "https://www.whitehouse.gov/administration/" in result.content
    assert result.provider_name == "synthetic-web"


def test_typo_officeholder_reuses_same_official_search_contract(monkeypatch):
    captured = []

    def mock_research(question, **options):
        captured.append({"question": question, **options})
        return SimpleNamespace(
            answer="Verified public officeholder [W1].",
            sources=[
                SimpleNamespace(
                    citation="[W1]",
                    title="Official website",
                    url="https://www.whitehouse.gov/administration/",
                )
            ],
            provider_name="synthetic-web",
            model_name="stub",
        )

    monkeypatch.setattr(chat_service, "research_web", mock_research)
    result = chat_service.execute_chat_turn(
        db=Mock(),
        conversation=SimpleNamespace(mode="normal", id="synthetic", user_id="synthetic"),
        message="What is the name of us presodent",
        web_mode="on",
    )
    assert result.provider_name == "synthetic-web"
    assert captured[0]["include_domains"] == ["whitehouse.gov"]
    assert captured[0]["time_range"] is None
