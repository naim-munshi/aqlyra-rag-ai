from fastapi.testclient import TestClient

from app.config.settings import settings
from app.main import app


client = TestClient(app)


def test_health_is_liveness() -> None:
    response = client.get(
        "/api/v1/health"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "aqlyra-rag-ai",
        "version": settings.VERSION,
    }


def test_readiness_checks_dependencies(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "UPLOAD_DIR",
        tmp_path,
    )

    response = client.get(
        "/api/v1/readiness"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ready"
    assert (
        payload["checks"]["database"]
        == "ready"
    )
    assert (
        payload["checks"]["storage"]
        == "ready"
    )


def test_readiness_fails_when_storage_missing(
    tmp_path,
    monkeypatch,
) -> None:
    missing = tmp_path / "missing"

    monkeypatch.setattr(
        settings,
        "UPLOAD_DIR",
        missing,
    )

    response = client.get(
        "/api/v1/readiness"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service is not ready"
    }
