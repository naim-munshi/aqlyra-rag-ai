"""Live first-party domain evidence search is owner-scoped, opted in, and non-authoritative."""
from datetime import datetime, timezone

import app.api.study_program_research as program_research
from app.api.dependencies import get_current_user
from app.main import app
from app.schemas.web_research import WebResearchResponse, WebResearchSource


def login(client, label: str) -> dict:
    app.dependency_overrides.pop(get_current_user, None)
    email = label + "@example.org"
    created = client.post("/api/v1/auth/register", json={
        "username": label, "email": email, "password": "TestOnlySecurePass123!",
    })
    assert created.status_code == 201, created.text
    authenticated = client.post("/api/v1/auth/login", json={
        "email": email, "password": "TestOnlySecurePass123!",
    })
    assert authenticated.status_code == 200, authenticated.text
    return {"Authorization": "Bearer " + authenticated.json()["access_token"]}


def setup_case(client, headers):
    created = client.post("/api/v1/study-abroad/cases", headers=headers, json={
        "nationality": "Bangladesh", "residence_country": "Japan",
        "destination_country": "Germany", "degree_level": "Bachelor's",
        "study_field": "Computer Science", "intake": "Winter 2027",
    })
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    school = client.post(
        f"/api/v1/study-abroad/cases/{case_id}/universities", headers=headers,
        json={
            "name": "Synthetic Research University",
            "program": "BSc Computer Science",
            "program_url": "https://catalog.example.edu/program?access=NOT-FOR-PROVIDER",
            "notes": "PRIVATE STUDENT NOTE NOT FOR PROVIDER",
        },
    )
    assert school.status_code == 201, school.text
    return case_id, school.json()["id"]


def evidence(question, max_sources, *, mode, include_domains=None):
    return WebResearchResponse(
        question=question, answer="Required IELTS 6.5 and minimum GPA 3.2 out of 4 [W1].",
        sources=[WebResearchSource(
            citation="[W1]", title="Official-host catalog (synthetic)",
            url="https://catalog.example.edu/requirements",
            excerpt="Required IELTS 6.5. Minimum GPA 3.2 out of 4.",
            published_date=None,
        )],
        provider_name="test", model_name="synthetic",
        searched_at=datetime.now(timezone.utc),
    )


def test_live_evidence_refresh_consent_ownership_domain_and_no_silent_writes(
    client, monkeypatch,
):
    alpha = login(client, "refreshowner")
    beta = login(client, "refreshother")
    case_id, school_id = setup_case(client, alpha)
    endpoint = f"/api/v1/study-abroad/cases/{case_id}/universities/{school_id}/refresh-evidence"
    captured = []

    def mock_research(question, max_sources, *, mode, include_domains=None):
        captured.append((question, max_sources, mode, include_domains))
        return evidence(question, max_sources, mode=mode, include_domains=include_domains)

    monkeypatch.setattr(program_research, "research_web", mock_research)
    assert client.post(endpoint, json={"confirm_share_program": True}).status_code == 401
    assert client.post(endpoint, headers=beta, json={"confirm_share_program": True}).status_code == 404
    assert client.post(endpoint, headers=alpha, json={}).status_code == 422
    assert captured == []
    result = client.post(endpoint, headers=alpha, json={
        "topic": "admissions", "confirm_share_program": True,
    })
    assert result.status_code == 200, result.text
    reply = result.json()
    assert reply["verification_status"] == "university_domain_evidence_needs_manual_review"
    assert reply["suggestions"][0]["suggested_facts"]["minimum_gpa"] == 3.2
    assert reply["suggestions"][0]["suggested_facts"]["minimum_language"]["score"] == 6.5
    assert reply["suggestions"][0]["status"] == "extracted_from_snippet_review_required"
    assert reply["report"]["sources"][0]["source_type"] == "shortlisted_program_domain_unverified"
    assert captured[0][1:] == (4, "deep", ["catalog.example.edu"])
    assert "NOT-FOR-PROVIDER" not in captured[0][0]
    assert "PRIVATE STUDENT NOTE" not in captured[0][0]
    assert len(captured[0][0]) <= 600
    # Research stores evidence; it cannot populate requirements without review.
    school = client.get(f"/api/v1/study-abroad/cases/{case_id}/universities", headers=alpha)
    assert school.status_code == 200
    assert school.json()[0]["requirements"] == {}
    research = client.get(f"/api/v1/study-abroad/cases/{case_id}/research", headers=alpha)
    assert research.status_code == 200
    assert len(research.json()) == 1


def test_live_evidence_refresh_rejects_search_engine_host_lookalike(client, monkeypatch):
    alpha = login(client, "refreshlookalike")
    case_id, school_id = setup_case(client, alpha)
    endpoint = f"/api/v1/study-abroad/cases/{case_id}/universities/{school_id}/refresh-evidence"

    def fake_evil(question, max_sources, *, mode, include_domains=None):
        return WebResearchResponse(
            question=question, answer="A suspicious source claims GPA 3.2 [W1].",
            sources=[WebResearchSource(
                citation="[W1]", title="Fake university",
                url="https://catalog.example.edu.attacker.com/claims",
                excerpt="minimum GPA 3.2 out of 4",
                published_date=None,
            )],
            provider_name="test", model_name="synthetic",
            searched_at=datetime.now(timezone.utc),
        )
    monkeypatch.setattr(program_research, "research_web", fake_evil)
    result = client.post(endpoint, headers=alpha, json={
        "topic": "admissions", "confirm_share_program": True,
    })
    assert result.status_code == 422
    research = client.get(f"/api/v1/study-abroad/cases/{case_id}/research", headers=alpha)
    assert research.json() == []
