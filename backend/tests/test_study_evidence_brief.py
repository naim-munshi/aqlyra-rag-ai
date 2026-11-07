"""Case-local evidence snapshot: access control and deterministic gaps."""
from datetime import datetime, timedelta, timezone

from app.models.study_case import StudyResearchReport


def login(client, name):
    email = name + "@example.org"
    created = client.post("/api/v1/auth/register", json={
        "username": name, "email": email,
        "password": "AcademicTestPassword123!",
    })
    assert created.status_code == 201, created.text
    result = client.post("/api/v1/auth/login", json={
        "email": email, "password": "AcademicTestPassword123!",
    })
    assert result.status_code == 200, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def make_case(client, auth):
    response = client.post("/api/v1/study-abroad/cases", headers=auth, json={
        "nationality": "Bangladesh", "residence_country": "Japan",
        "destination_country": "Germany", "degree_level": "Bachelor's",
        "study_field": "Computer Science", "intake": "2028",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_brief_is_private_and_does_not_invent_evidence(client):
    alice = login(client, "briefalice")
    bob = login(client, "briefbob")
    case_id = make_case(client, alice)
    endpoint = f"/api/v1/study-abroad/cases/{case_id}/evidence-brief"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=bob).status_code == 404
    response = client.get(endpoint, headers=alice)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "planning_snapshot_unverified"
    assert data["summary"]["shortlisted_programs"] == 0
    assert data["summary"]["linked_ready_documents"] == 0
    assert data["programs"] == []
    assert data["saved_source_links"] == []
    assert data["privacy"] == {
        "external_requests_made": 0,
        "document_text_accessed": False,
        "document_excerpts_shared": False,
    }


def test_real_program_gaps_and_stale_source_links(client, db_session):
    alice = login(client, "briefmatchalice")
    case_id = make_case(client, alice)
    root = f"/api/v1/study-abroad/cases/{case_id}"
    school = client.post(root + "/universities", headers=alice, json={
        "name": "Synthetic University", "program": "Computer Science",
        "program_url": "https://catalog.example.edu/program?draft=42",
    })
    assert school.status_code == 201, school.text
    school_id = school.json()["id"]
    assert client.patch(root + "/applicant-facts", headers=alice, json={
        "gpa": 3.4, "gpa_scale": 4,
        "language": {"test": "IELTS", "score": 7},
    }).status_code == 200
    assert client.patch(
        root + f"/universities/{school_id}/requirements", headers=alice,
        json={
            "minimum_gpa": 3.6, "gpa_scale": 4,
            "minimum_language": {"test": "IELTS", "score": 6.5},
        },
    ).status_code == 200
    db_session.add(StudyResearchReport(
        case_id=case_id, topic="admissions", question="Catalog research",
        answer="Inspect the admissions source [W1].",
        sources=[{
            "citation": "[W1]", "title": "Catalog",
            "url": "https://catalog.example.edu/admissions?view=old",
            "source_type": "unverified_external_source",
        }],
        searched_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=90),
    ))
    db_session.commit()
    response = client.get(root + "/evidence-brief", headers=alice)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["summary"]["shortlisted_programs"] == 1
    assert data["summary"]["programs_with_reported_gaps"] == 1
    assert data["summary"]["stale_research_topics"] == 1
    comparison = data["programs"][0]
    assert comparison["gap_count"] == 1
    assert comparison["matched_count"] == 1
    assert comparison["unknown_count"] == 2
    assert comparison["program_url"] == "https://catalog.example.edu/program"
    assert data["saved_source_links"][0]["url"] == "https://catalog.example.edu/admissions"
    assert data["saved_source_links"][0]["stale"] is True
    assert "view=old" not in response.text
    assert "draft=42" not in response.text
