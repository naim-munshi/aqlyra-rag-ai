"""Actual program comparison, citation binding, and two-JWT tenant isolation."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.dependencies import get_current_user
from app.main import app
import app.api.study_abroad as study_api
from app.schemas.study_abroad import StudyApplicantFacts, ProgramRequirements
from app.schemas.web_research import WebResearchResponse, WebResearchSource
from app.study_abroad.program_matcher import matching_source_host

PROFILE = {
    "nationality": "Bangladesh",
    "residence_country": "Japan",
    "destination_country": "Germany",
    "degree_level": "Bachelor's",
    "study_field": "Computer Science",
    "intake": "2027",
}


def _jwt(client, identity):
    app.dependency_overrides.pop(get_current_user, None)
    email = identity + "@example.org"
    r = client.post("/api/v1/auth/register", json={
        "username": identity, "email": email, "password": "SyntheticStrongPassword123!",
    })
    assert r.status_code == 201, r.text
    token = client.post("/api/v1/auth/login", json={
        "email": email, "password": "SyntheticStrongPassword123!",
    })
    assert token.status_code == 200, token.text
    return {"Authorization": "Bearer " + token.json()["access_token"]}


def _case(client, headers):
    r = client.post("/api/v1/study-abroad/cases", json=PROFILE, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _school(client, headers, case, name="Synthetic Academy"):
    r = client.post(
        f"/api/v1/study-abroad/cases/{case}/universities", headers=headers,
        json={
            "name": name,
            "program": "BSc CS Transfer",
            "program_url": "https://catalog.example.edu/program",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_real_two_jwt_match_engine_compares_without_unsupported_equivalences(client):
    alpha = _jwt(client, "studymatchalpha")
    beta = _jwt(client, "studymatchbeta")
    case = _case(client, alpha)
    other_case = _case(client, beta)
    school = _school(client, alpha, case)
    root = f"/api/v1/study-abroad/cases/{case}"
    fact = {
        "gpa": 3.4, "gpa_scale": 4,
        "annual_budget": 1100000, "currency": "JPY",
        "language": {"test": "IELTS", "score": 7.0},
        "transfer_requested": True, "completed_credits": 58,
    }
    assert client.patch(root + "/applicant-facts", json=fact).status_code == 401
    assert client.patch(root + "/applicant-facts", headers=beta, json=fact).status_code == 404
    saved = client.patch(root + "/applicant-facts", headers=alpha, json=fact)
    assert saved.status_code == 200, saved.text
    assert saved.json()["gpa"] == 3.4
    req = {
        "minimum_gpa": 3.5, "gpa_scale": 4,
        "minimum_language": {"test": "IELTS", "score": 6.5},
        "annual_tuition": 8000, "currency": "USD",
        "transfer_policy": "no",
    }
    edit = root + f"/universities/{school}/requirements"
    assert client.patch(edit, headers=beta, json=req).status_code == 404
    assert client.patch(edit, headers=alpha, json=req).status_code == 200
    assert client.get(root + "/matches", headers=beta).status_code == 404
    response = client.get(root + "/matches", headers=alpha)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["profile"]["gpa"] == 3.4
    assert data["case_id"] == case
    assert len(data["programs"]) == 1
    item = data["programs"][0]
    assert item["assessment"] == "possible_gaps"
    assert item["gap_count"] == 2
    assert item["matched_count"] == 1
    assert item["unknown_count"] == 1
    checks = {c["criterion"]: c["status"] for c in item["criteria"]}
    assert checks == {
        "gpa": "reported_gap",
        "language": "reported_match",
        "tuition": "unknown",
        "transfer": "reported_gap",
    }
    assert item["provenance"] == "self_reported_unverified"
    assert "not admission probability" in data["disclaimer"]
    assert client.get(f"/api/v1/study-abroad/cases/{other_case}/matches", headers=beta).json()["programs"] == []
    # Invalid grader and currency pairs fail closed.
    assert client.patch(root + "/applicant-facts", headers=alpha, json={
        "gpa": 7, "gpa_scale": 4,
    }).status_code == 422
    assert client.patch(root + "/applicant-facts", headers=alpha, json={
        "annual_budget": 100000,
    }).status_code == 422
    assert client.patch(edit, headers=alpha, json={
        "minimum_language": {"test": "IELTS", "score": 11},
    }).status_code == 422


def test_source_citation_must_be_owner_case_and_first_party_university(client, monkeypatch):
    alpha = _jwt(client, "studycitalpha")
    beta = _jwt(client, "studycitbeta")
    case_a = _case(client, alpha)
    case_b = _case(client, beta)
    u = _school(client, alpha, case_a)
    q = []
    def synthetic_research(question, max_sources, *, mode, include_domains=None):
        q.append(question)
        return WebResearchResponse(
            question=question,
            answer="The official program's published requirements must be checked for the selected intake [W1].",
            sources=[
                WebResearchSource(
                    citation="[W1]", title="Official university catalog",
                    url="https://catalog.example.edu/admissions",
                    excerpt="This synthetic academic page requires individual review.",
                    published_date=None,
                ),
                WebResearchSource(
                    citation="[W2]", title="Lookalike page",
                    url="https://catalog.example.edu.attacker.com/claims",
                    excerpt="Untrusted.",
                    published_date=None,
                ),
            ],
            provider_name="synthetic", model_name="test",
            searched_at=datetime.now(timezone.utc),
        )
    monkeypatch.setattr(study_api, "research_web", synthetic_research)
    end_a = f"/api/v1/study-abroad/cases/{case_a}"
    end_b = f"/api/v1/study-abroad/cases/{case_b}"
    ok = client.post(end_a + "/research", headers=alpha, json={
        "topic": "admissions", "focus_university_id": u,
        "confirm_share_profile": True,
    })
    assert ok.status_code == 200, ok.text
    report_id = ok.json()["id"]
    assert len(q) == 1
    assert "catalog.example.edu" not in q[0]  # private URL was never transmitted
    editing = end_a + f"/universities/{u}/requirements"
    bad_src = client.patch(editing, headers=alpha, json={
        "minimum_gpa": 3, "gpa_scale": 4,
        "evidence_report_id": report_id,
        "evidence_citation": "[W2]",
    })
    assert bad_src.status_code == 422
    foreign = client.patch(editing, headers=beta, json={
        "minimum_gpa": 3, "gpa_scale": 4,
        "evidence_report_id": report_id,
        "evidence_citation": "[W1]",
    })
    assert foreign.status_code == 404
    good = client.patch(editing, headers=alpha, json={
        "minimum_gpa": 3, "gpa_scale": 4,
        "evidence_report_id": report_id, "evidence_citation": "[W1]",
    })
    assert good.status_code == 200, good.text
    match = client.get(end_a + "/matches", headers=alpha).json()["programs"][0]
    assert match["provenance"] == "source_linked_unverified"
    assert match["evidence_url"] == "https://catalog.example.edu/admissions"
    assert match["assessment"] == "insufficient_evidence"  # no applicant GPA
    candidates = client.get(end_a + "/program-candidates", headers=alpha)
    assert candidates.status_code == 200
    assert candidates.json()[0]["status"] == "research_link_only_not_verified_program"
    assert client.get(end_a + "/program-candidates", headers=beta).status_code == 404
    assert client.get(end_b + "/program-candidates", headers=beta).json() == []


def test_jlpt_order_never_converts_to_ielts_and_empty_program_never_scores(client):
    alpha = _jwt(client, "studymatchjlpt")
    case = _case(client, alpha)
    school = _school(client, alpha, case)
    base = f"/api/v1/study-abroad/cases/{case}"
    empty = client.get(base + "/matches", headers=alpha).json()["programs"][0]
    assert empty["assessment"] == "insufficient_evidence"
    assert empty["comparable_count"] == 0
    assert client.patch(base + "/applicant-facts", headers=alpha, json={
        "language": {"test": "JLPT", "level": "N2"},
    }).status_code == 200
    url = base + f"/universities/{school}/requirements"
    assert client.patch(url, headers=alpha, json={
        "minimum_language": {"test": "JLPT", "level": "N3"},
    }).status_code == 200
    status = client.get(base + "/matches", headers=alpha).json()["programs"][0]
    assert status["matched_count"] == 1
    assert status["assessment"] == "potential_match_unverified"
    assert client.patch(url, headers=alpha, json={
        "minimum_language": {"test": "IELTS", "score": 6.5},
    }).status_code == 200
    different = client.get(base + "/matches", headers=alpha).json()["programs"][0]
    assert different["matched_count"] == 0
    assert different["criteria"][1]["status"] == "unknown"


def test_safe_source_host_rejects_lookalikes_and_credentials():
    assert matching_source_host(
        "https://admissions.example.edu/program", "https://example.edu/requirements"
    )
    for bad in (
        "https://admissions.example.edu.attacker.com/requirements",
        "http://example.edu",
        "https://user:pass@example.edu/requirements",
        "https://example.net",
        "https://example.edu:8999/requirements",
    ):
        assert not matching_source_host("https://example.edu/program", bad)
