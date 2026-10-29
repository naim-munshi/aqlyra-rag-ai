"""Study Abroad route activation in the scoped Core backend (schema already migrated)."""
from app.database.base import Base
from app.main import app

def test_study_abroad_route_is_registered(client):
    # Public workflow metadata; user-owned journeys still require auth.
    assert client.get("/api/v1/study-abroad/workflows").status_code == 200
    assert client.get("/api/v1/study-abroad/cases").status_code == 401
    assert any("study-abroad" in getattr(r, "path", "") for r in app.routes)

def test_study_abroad_tables_are_registered():
    for table in (
        "study_cases", "study_case_documents",
        "study_research_reports", "study_universities",
    ):
        assert table in Base.metadata.tables
