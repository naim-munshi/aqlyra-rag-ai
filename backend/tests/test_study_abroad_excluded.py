"""Study Abroad is intentionally not part of the scoped Aqlyra release."""
from app.database.base import Base
from app.main import app


def test_study_abroad_routes_are_not_registered(client):
    assert client.get("/api/v1/study-abroad/workflows").status_code == 404
    assert not any(
        "study-abroad" in getattr(route, "path", "")
        for route in app.routes
    )


def test_study_abroad_tables_are_not_registered():
    for name in (
        "study_cases",
        "study_case_documents",
        "study_research_reports",
        "study_universities",
    ):
        assert name not in Base.metadata.tables
