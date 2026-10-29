"""Readiness must not confuse a writable ephemeral disk with durable uploads."""
import app.api.v1.health as health_module
from app.config.settings import settings


def test_readiness_reports_write_disabled_without_probing_ephemeral_disk(
    client, monkeypatch, tmp_path,
):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(health_module, "local_writes_permitted", lambda: False)
    monkeypatch.setattr(health_module, "artifact_writes_permitted", lambda: False)

    def unexpected_disk_probe(**kwargs):
        raise AssertionError("Disabled local uploads must not probe the disk")

    monkeypatch.setattr(health_module.tempfile, "NamedTemporaryFile", unexpected_disk_probe)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["checks"]["storage"] == "writes_disabled"
    assert response.json()["checks"]["artifact_storage"] == "writes_disabled"
    assert response.json()["checks"]["cloud_uploads"] == "disabled"


def test_readiness_reports_verified_local_write_capability(
    client, monkeypatch, tmp_path,
):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["checks"]["storage"] == "ready"
    assert response.json()["checks"]["artifact_storage"] == "ready"
