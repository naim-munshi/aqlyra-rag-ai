"""Study Advisor is strictly case-private and does not invent admissions facts."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.dependencies import get_current_user
from app.main import app
import app.api.study_abroad as study_api
from app.schemas.web_research import WebResearchResponse, WebResearchSource
from app.study_abroad.advisor import build_study_advisor
from app.study_abroad.workflows import initial_checklist, research_question


PROFILE = {
    "workflow": "student",
    "nationality": "Bangladesh",
    "residence_country": "Japan",
    "destination_country": "Germany",
    "degree_level": "Master's",
    "study_field": "Computer Science",
    "intake": "Winter 2027",
}


def _login(client, label: str) -> dict[str, str]:
    app.dependency_overrides.pop(get_current_user, None)
    email = label + "@example.org"
    registered = client.post("/api/v1/auth/register", json={
        "username": label,
        "email": email,
        "password": "SyntheticSecurePass123!",
    })
    assert registered.status_code == 201, registered.text
    session = client.post("/api/v1/auth/login", json={
        "email": email, "password": "SyntheticSecurePass123!",
    })
    assert session.status_code == 200, session.text
    return {"Authorization": "Bearer " + session.json()["access_token"]}


def _case(client, headers):
    response = client.post("/api/v1/study-abroad/cases", json=PROFILE, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_advisor_is_authenticated_owner_scoped_and_explainable(client):
    alice = _login(client, "advisor-alice")
    bob = _login(client, "advisor-bob")
    case = _case(client, alice)
    url = f"/api/v1/study-abroad/cases/{case['id']}/advisor"
    assert client.get(url).status_code == 401
    denied = client.get(url, headers=bob)
    assert denied.status_code == 404
    result = client.get(url, headers=alice)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["case_id"] == case["id"]
    assert data["reviewed_checklist_count"] == 0
    assert data["total_checklist_count"] == 10
    assert data["linked_document_count"] == 0
    assert data["shortlisted_university_count"] == 0
    assert data["verification_status"] == "planning_only_not_eligibility_verified"
    assert data["next_actions"][0]["id"] == "shortlist"
    assert all("eligib" not in step["title"].lower() or
               step["urgency"] != "urgent" for step in data["next_actions"])
    reviewed = client.patch(
        f"/api/v1/study-abroad/cases/{case['id']}/checklist/academic",
        json={"state": "reviewed"}, headers=alice,
    )
    assert reviewed.status_code == 200
    fresh = client.get(url, headers=alice)
    assert fresh.json()["reviewed_checklist_count"] == 1
    assert fresh.json()["verification_status"] == "planning_only_not_eligibility_verified"


def test_advisor_deadlines_are_only_user_entered_and_research_gets_stale(
):
    now = datetime(2027, 2, 1, tzinfo=timezone.utc)
    case = SimpleNamespace(id="case-1", checklist=initial_checklist())
    university = SimpleNamespace(
        id="u1", name="Synthetic University", deadline="2027-02-15",
        application_status="shortlisted",
    )
    stale = SimpleNamespace(
        topic="admissions", searched_at=now - timedelta(days=90),
        sources=[{"citation": "[W1]", "source_type": "unverified_external_source"}],
    )
    report = build_study_advisor(
        case=case, universities=[university], reports=[stale],
        linked_document_count=2, now=now,
    )
    assert report["deadline_warnings"][0]["days_remaining"] == 14
    assert report["deadline_warnings"][0]["verification_status"] == "user_entered_unverified"
    assert report["next_actions"][0]["urgency"] == "urgent"
    assert report["research_freshness"][0]["stale"]
    assert report["research_freshness"][0]["government_domain_sources"] == 0
    assert report["verification_status"] == "planning_only_not_eligibility_verified"
    assert any(a["research_topic"] == "admissions" for a in report["next_actions"])


def test_focused_research_cannot_use_unowned_or_unsaved_program(client, monkeypatch):
    alice = _login(client, "advisor-focus-alice")
    bob = _login(client, "advisor-focus-bob")
    a = _case(client, alice)
    b = _case(client, bob)
    url_a = f"/api/v1/study-abroad/cases/{a['id']}/research"
    shortlist_url_b = f"/api/v1/study-abroad/cases/{b['id']}/universities"
    foreign = client.post(shortlist_url_b, headers=bob, json={
        "name": "Synthetic University B",
        "program": "Synthetic MSc Engineering",
        "program_url": "https://example.edu/study?token=PRIVATE-NOT-SHARED",
        "notes": "Private student comment",
    })
    assert foreign.status_code == 201, foreign.text
    calls = []
    def research(question, max_sources, *, mode, include_domains=None):
        calls.append(question)
        return WebResearchResponse(
            question=question,
            answer="Verify the official school guidance [W1].",
            sources=[WebResearchSource(
                citation="[W1]", title="Synthetic program page",
                url="https://example.edu/admissions",
                excerpt="Verification is required", published_date=None,
            )],
            provider_name="synthetic", model_name="test",
            searched_at=datetime.now(timezone.utc),
        )
    monkeypatch.setattr(study_api, "research_web", research)
    wrong_case = client.post(url_a, headers=alice, json={
        "topic": "transfer", "focus_university_id": foreign.json()["id"],
        "confirm_share_profile": True,
    })
    assert wrong_case.status_code == 404
    assert calls == []
    saved = client.post(
        f"/api/v1/study-abroad/cases/{a['id']}/universities",
        headers=alice,
        json={
            "name": "Synthetic University A",
            "program": "BSc Computer Science",
            "program_url": "https://example.edu/program?token=PRIVATE-NOT-SHARED",
            "notes": "Synthetic passport-sensitive description not for search",
        },
    )
    assert saved.status_code == 201, saved.text
    target = saved.json()["id"]
    no_consent = client.post(url_a, headers=alice, json={
        "topic": "transfer", "focus_university_id": target,
    })
    assert no_consent.status_code == 422
    assert calls == []
    accepted = client.post(url_a, headers=alice, json={
        "topic": "transfer", "focus_university_id": target,
        "confirm_share_profile": True,
    })
    assert accepted.status_code == 200, accepted.text
    assert len(calls) == 1
    assert "Synthetic University A" in calls[0]
    assert "BSc Computer Science" in calls[0]
    assert "credit" in calls[0].lower()
    assert "PRIVATE-NOT-SHARED" not in calls[0]
    assert "passport-sensitive" not in calls[0]
    assert len(calls[0]) <= 600
    assert accepted.json()["verification_status"] == "needs_official_verification"


def test_new_research_topics_and_unknown_deadlines_are_safe():
    case = SimpleNamespace(**PROFILE)
    for topic in ("language", "costs", "transfer"):
        question = research_question(topic, case, focus=("Synthetic School", "MSc AI"))
        assert "Bangladesh" in question and "Japan" in question
        assert "Synthetic School" in question
        assert len(question) <= 600
        assert "do not guarantee eligibility" in question.lower()
    model = SimpleNamespace(id="c", checklist=initial_checklist())
    for deadline in ("2027-02-99", "2027-2-1", "next semester", ""):
        uni = SimpleNamespace(
            id="u", name="Synthetic U", deadline=deadline,
            application_status="researching",
        )
        result = build_study_advisor(
            case=model, universities=[uni], reports=[],
            linked_document_count=0,
            now=datetime(2027, 2, 1, tzinfo=timezone.utc),
        )
        assert result["deadline_warnings"] == []
