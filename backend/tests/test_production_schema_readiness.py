"""Release health contracts: liveness differs from production readiness.

The unit-test database uses SQLAlchemy metadata, not an applied Alembic
release revision. A production process must reject that as unready even
though the database accepts SELECT 1.
"""
from app.config.settings import settings


def test_health_liveness_does_not_require_migrated_database(client):
    result = client.get("/api/v1/health")
    assert result.status_code == 200
    assert result.json()["status"] == "healthy"


def test_production_readiness_refuses_unmigrated_database(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)

    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
