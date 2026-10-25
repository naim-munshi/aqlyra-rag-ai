"""Privacy, CRUD, upload, dynamic sources and future workflow safety."""
from datetime import datetime, timezone
from io import BytesIO

from app.api.dependencies import get_current_user
import app.api.study_abroad as study_api
from app.main import app
from app.models.user import User
from app.schemas.web_research import WebResearchResponse, WebResearchSource
from app.study_abroad.workflows import research_question, WORKFLOWS


def user(db, email: str) -> User:
    obj = User(email=email, username=email.split("@")[0],
               hashed_password="hashed-placeholder")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def authenticate(usr: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: usr


def example_profile() -> dict:
    return {
      "workflow": "student",
      "nationality": "Bangladesh",
      "residence_country": "Japan",
      "destination_country": "Germany",
      "degree_level": "Master's",
      "study_field": "Computer Science",
      "intake": "Winter 2027",
    }


def test_workflows_default_to_student_only(client):
    result = client.get("/api/v1/study-abroad/workflows")
    assert result.status_code == 200
    flows = {entry["id"]: entry for entry in result.json()}
    assert flows["student"]["enabled"] is True
    assert flows["job"]["enabled"] is False


def test_private_case_crud_and_checklist(client, db_session):
    alice = user(db_session, "study-owner@example.org")
    bob = user(db_session, "study-outsider@example.org")
    authenticate(alice)
    created = client.post("/api/v1/study-abroad/cases", json=example_profile())
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["checklist"]["passport"]["state"] == "needs_verification"
    assert len(case["checklist"]) == 10
    assert client.get("/api/v1/study-abroad/cases").json()[0]["id"] == case["id"]

    update = client.patch(f"/api/v1/study-abroad/cases/{case['id']}",
                          json={"stage": "embassy", "notes": "Check official embassy website"})
    assert update.status_code == 200
    assert update.json()["stage"] == "embassy"
    assert client.patch(f"/api/v1/study-abroad/cases/{case['id']}",
                        json={"stage": "job"}).status_code == 422

    checklist = client.patch(f"/api/v1/study-abroad/cases/{case['id']}/checklist/passport",
        json={"state": "reviewed", "evidence_url": "https://www.gov.uk/student-visa/documents-you-must-provide"})
    assert checklist.status_code == 200
    assert checklist.json()["checklist"]["passport"]["state"] == "reviewed"
    assert client.patch(f"/api/v1/study-abroad/cases/{case['id']}/checklist/passport",
        json={"state": "reviewed", "evidence_url": "http://127.0.0.1/private"}).status_code == 422

    authenticate(bob)
    assert client.get(f"/api/v1/study-abroad/cases/{case['id']}").status_code == 404
    assert client.patch(f"/api/v1/study-abroad/cases/{case['id']}",
                        json={"notes": "attack"}).status_code == 404
    assert client.get(f"/api/v1/study-abroad/cases/{case['id']}/documents").status_code == 404
    assert client.get(f"/api/v1/study-abroad/cases/{case['id']}/research").status_code == 404
    assert client.post(f"/api/v1/study-abroad/cases/{case['id']}/research",
                       json={"topic": "visa"}).status_code == 404
    assert client.delete(f"/api/v1/study-abroad/cases/{case['id']}").status_code == 404
    assert client.get("/api/v1/study-abroad/cases").json() == []

    authenticate(alice)
    assert client.delete(f"/api/v1/study-abroad/cases/{case['id']}").status_code == 204
    assert client.get("/api/v1/study-abroad/cases").json() == []


def test_link_only_user_owned_processed_files(client, db_session):
    alice = user(db_session, "files-owner@example.org")
    bob = user(db_session, "files-other@example.org")
    authenticate(alice)
    case = client.post("/api/v1/study-abroad/cases", json=example_profile()).json()
    uploaded = client.post("/api/v1/documents/upload",
                           files={"file": ("academic.txt", BytesIO(b"A high school transcript."), "text/plain")})
    assert uploaded.status_code == 201, uploaded.text
    doc = uploaded.json()
    before_processing = client.post(f"/api/v1/study-abroad/cases/{case['id']}/documents",
             json={"document_id": doc["id"], "checklist_key": "academic"})
    assert before_processing.status_code == 409
    processed = client.post(f"/api/v1/documents/{doc['id']}/process")
    assert processed.status_code == 200, processed.text
    attached = client.post(f"/api/v1/study-abroad/cases/{case['id']}/documents",
             json={"document_id": doc["id"], "checklist_key": "academic"})
    assert attached.status_code == 201, attached.text
    assert attached.json()["status"] == "ready"
    linked = client.get(f"/api/v1/study-abroad/cases/{case['id']}/documents")
    assert len(linked.json()) == 1
    assert client.get(f"/api/v1/study-abroad/cases/{case['id']}").json()[
       "checklist"]["academic"]["document_id"] == doc["id"]

    authenticate(bob)
    other_case = client.post("/api/v1/study-abroad/cases", json=example_profile()).json()
    denied = client.post(f"/api/v1/study-abroad/cases/{other_case['id']}/documents",
             json={"document_id": doc["id"], "checklist_key": "academic"})
    assert denied.status_code == 404
    authenticate(alice)
    detached = client.delete(f"/api/v1/study-abroad/cases/{case['id']}/documents/{doc['id']}")
    assert detached.status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 200


def test_research_is_sourced_and_scoped_without_private_documents(
    client, db_session, monkeypatch,
):
    alice = user(db_session, "source-owner@example.org")
    bob = user(db_session, "source-other@example.org")
    authenticate(alice)
    case = client.post("/api/v1/study-abroad/cases", json=example_profile()).json()
    captured = []
    def mock_research(question: str, max_sources: int, *, mode: str, include_domains=None):
        captured.append((question, max_sources, mode, include_domains))
        return WebResearchResponse(
            question=question, answer="Verify official rules [W1].",
            sources=[WebResearchSource(
              citation="[W1]", title="Government guide",
              url="https://www.auswaertiges-amt.de/en/visa-service",
              excerpt="Official rules must be checked.", published_date=None)],
            provider_name="test", model_name="fake", searched_at=datetime.now(timezone.utc),
        )
    monkeypatch.setattr(study_api, "research_web", mock_research)
    missing_consent = client.post(
        f"/api/v1/study-abroad/cases/{case['id']}/research",
        json={"topic": "visa"},
    )
    assert missing_consent.status_code == 422
    assert captured == []
    report = client.post(f"/api/v1/study-abroad/cases/{case['id']}/research",
                         json={"topic": "visa", "confirm_share_profile": True})
    assert report.status_code == 200, report.text
    assert report.json()["verification_status"] == "needs_official_verification"
    assert report.json()["sources"][0]["citation"] == "[W1]"
    assert report.json()["sources"][0]["source_type"] == "official_authority_domain"
    assert "Bangladesh" in captured[0][0]
    assert "Japan" in captured[0][0]
    assert "Germany" in captured[0][0]
    assert captured[0][1:3] == (4, "deep")
    assert "auswaertiges-amt.de" in captured[0][3]
    stored = client.get(f"/api/v1/study-abroad/cases/{case['id']}/research")
    assert len(stored.json()) == 1
    authenticate(bob)
    assert client.get(f"/api/v1/study-abroad/cases/{case['id']}/research").status_code == 404


def test_research_profiles_do_not_fake_universal_requirements():
    class Profile:
        nationality = "Bangladesh"
        residence_country = "Japan"
        destination_country = "Germany"
        degree_level = "Masters"
        study_field = "AI"
        intake = "2027"
    for topic in ("universities", "admissions", "scholarships", "visa",
                  "embassy", "predeparture"):
        prompt = research_question(topic, Profile())
        assert "Bangladesh" in prompt and "Japan" in prompt and "Germany" in prompt
        assert len(prompt) <= 600
    assert not WORKFLOWS["job"].enabled


def test_university_shortlist_privacy_and_status(client, db_session):
    owner = user(db_session, "university-owner@example.org")
    outsider = user(db_session, "university-outsider@example.org")
    authenticate(owner)
    case = client.post("/api/v1/study-abroad/cases", json=example_profile()).json()
    path = f"/api/v1/study-abroad/cases/{case['id']}/universities"
    bad = client.post(path, json={
        "name": "Example College",
        "program": "Computer Science",
        "program_url": "http://127.0.0.1/internal",
    })
    assert bad.status_code == 422
    saved = client.post(path, json={
        "name": "Example College", "program": "Computer Science",
        "program_url": "https://example.edu/program",
        "deadline": "2027-01-15",
    })
    assert saved.status_code == 201, saved.text
    item = saved.json()
    assert item["application_status"] == "researching"
    assert len(client.get(path).json()) == 1
    changed = client.patch(path + "/" + item["id"],
                          json={"application_status": "applied"})
    assert changed.status_code == 200
    assert changed.json()["application_status"] == "applied"
    assert client.patch(path + "/" + item["id"],
                        json={"application_status": "admitted_for_sure"}).status_code == 422
    authenticate(outsider)
    assert client.get(path).status_code == 404
    assert client.patch(path + "/" + item["id"],
                        json={"application_status": "offer"}).status_code == 404
    assert client.delete(path + "/" + item["id"]).status_code == 404
    authenticate(owner)
    assert client.delete(path + "/" + item["id"]).status_code == 204
    assert client.get(path).json() == []


def test_official_source_gates_and_lookalikes():
    from app.study_abroad.evidence_policy import (
        OfficialEvidenceMissing, authority_domains, classify_sources,
        matches_authority,
    )
    from app.schemas.web_research import WebResearchSource
    import pytest
    domains = authority_domains("Germany")
    assert "auswaertiges-amt.de" in domains
    assert matches_authority("https://www.auswaertiges-amt.de/en/visa-service", domains)
    assert not matches_authority("https://auswaertiges-amt.de.attacker.com/visa", domains)
    assert not matches_authority("http://auswaertiges-amt.de/visa", domains)
    assert not matches_authority("https://auswaertiges-amt.de@evil.com/visa", domains)
    bad = WebResearchSource(
        citation="[W1]", title="Untrusted blog",
        url="https://visa-help.example.com/blog", excerpt="Fake official advice",
    )
    good = WebResearchSource(
        citation="[W2]", title="German Federal Foreign Office",
        url="https://www.auswaertiges-amt.de/en/visa-service", excerpt="Visa rules",
    )
    with pytest.raises(OfficialEvidenceMissing):
        classify_sources("visa", "Germany", [bad])
    with pytest.raises(OfficialEvidenceMissing):
        classify_sources("embassy", "Unregistered Country", [good])
    result = classify_sources("visa", "Germany", [bad, good])
    assert result[0]["source_type"] == "unverified_external_source"
    assert result[1]["source_type"] == "official_authority_domain"
    assert classify_sources("universities", "Germany", [bad])[0][
        "source_type"] == "unverified_external_source"


def test_sensitive_study_research_without_official_source_fails_closed(
    client, db_session, monkeypatch,
):
    from app.schemas.web_research import WebResearchResponse, WebResearchSource
    owner = user(db_session, "visa-evidence-owner@example.org")
    authenticate(owner)
    item = client.post("/api/v1/study-abroad/cases", json=example_profile()).json()
    calls = []
    def fake_provider(question: str, max_sources: int, *, mode: str, include_domains=None):
        calls.append((question, include_domains))
        return WebResearchResponse(
            question=question, answer="Questionable requirements [W1].",
            sources=[WebResearchSource(
                citation="[W1]", title="Nonofficial source",
                url="https://randomblog.org/requirements", excerpt="Unsupported claims",
            )],
            provider_name="test", model_name="fake",
            searched_at=datetime.now(timezone.utc),
        )
    monkeypatch.setattr(study_api, "research_web", fake_provider)
    response = client.post(
        f"/api/v1/study-abroad/cases/{item['id']}/research",
        json={"topic": "visa", "confirm_share_profile": True},
    )
    assert response.status_code == 422
    assert calls[0][1] and "auswaertiges-amt.de" in calls[0][1]
    assert client.get(
        f"/api/v1/study-abroad/cases/{item['id']}/research"
    ).json() == []
