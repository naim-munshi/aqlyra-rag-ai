"""Focused natural-language research must remain consensual, bounded and cited."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.dependencies import get_current_user
from app.main import app
import app.api.study_abroad as study_api
from app.models.user import User
from app.schemas.study_abroad import StudyResearchCreate
from app.schemas.web_research import WebResearchResponse, WebResearchSource
from app.study_abroad.workflows import research_question


PROFILE = {
    "workflow": "student",
    "nationality": "Bangladesh",
    "residence_country": "Japan",
    "destination_country": "Germany",
    "degree_level": "Master's",
    "study_field": "Computer Science",
    "intake": "Winter 2027",
}


@pytest.mark.parametrize("private_question", [
    "Please use https://example.edu/?secret=private to recommend schools.",
    "Contact my personal mail test.student@example.com about admission",
    "My passport number 12345678912345 is valid for Germany?",
    "My bank account is 987654321019 for the scholarship",
])
def test_custom_research_rejects_identifiers_and_urls(private_question):
    with pytest.raises(ValidationError):
        StudyResearchCreate(
            topic="admissions", confirm_share_profile=True,
            specific_question=private_question,
        )


def test_custom_question_survives_bounded_profile_and_honors_official_evidence():
    profile = SimpleNamespace(**PROFILE)
    actual = "Do any programs accept academic credits from a Japanese college?"
    query = research_question(
        "transfer", profile,
        focus=("Synthetic University", "Information Engineering"),
        specific_question=actual,
    )
    assert actual in query
    assert "Bangladesh" in query and "Japan" in query
    assert "Synthetic University" in query
    assert "do not guarantee eligibility" in query.lower()
    assert len(query) <= 600

    oversized = StudyResearchCreate(
        topic="visa", confirm_share_profile=True,
        specific_question="How do I verify which consulate handles student visas for my residence?",
    )
    assert oversized.specific_question


def test_custom_question_saves_only_cited_research_after_explicit_consent(
    client, db_session, monkeypatch,
):
    owner = User(
        email="focused-research@example.org",
        username="focusedresearch",
        hashed_password="synthetic-hash",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        case_resp = client.post("/api/v1/study-abroad/cases", json=PROFILE)
        assert case_resp.status_code == 201, case_resp.text
        case_id = case_resp.json()["id"]
        sent = []
        def mocked_research(question: str, max_sources: int, *, mode: str, include_domains=None):
            sent.append(question)
            return WebResearchResponse(
                question=question,
                answer="Only the official program can confirm eligibility [W1].",
                sources=[WebResearchSource(
                    citation="[W1]", title="Synthetic official program",
                    url="https://example.edu/admissions",
                    excerpt="Admission requirements depend on the program",
                    published_date=None,
                )],
                provider_name="synthetic",
                model_name="test",
                searched_at=datetime.now(timezone.utc),
            )
        monkeypatch.setattr(study_api, "research_web", mocked_research)
        url = f"/api/v1/study-abroad/cases/{case_id}/research"
        data = {
            "topic": "transfer",
            "specific_question": "Can I transfer completed Japanese university credits?",
        }
        refused = client.post(url, json=data)
        assert refused.status_code == 422
        assert sent == []
        accepted = client.post(url, json={
            **data, "confirm_share_profile": True,
        })
        assert accepted.status_code == 200, accepted.text
        assert "Can I transfer completed Japanese university credits?" in sent[0]
        assert len(sent[0]) <= 600
        assert accepted.json()["verification_status"] == "needs_official_verification"
        assert accepted.json()["sources"][0]["citation"] == "[W1]"
        assert len(client.get(url).json()) == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
