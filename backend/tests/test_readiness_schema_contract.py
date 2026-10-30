"""Offline regression: connection-only readiness must not claim RAG is ready.

No production secrets, network calls or schema mutations.
"""
from app.config.settings import settings
from app.api.v1 import health as health_module


EXPECTED_HEAD = "d4ec2f9b7860"


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Database:
    def __init__(self, revision, schema):
        self.revision = revision
        self.schema = schema
        self.closed = False

    def execute(self, query):
        sql = str(query)
        if "alembic_version" in sql:
            return _Scalar(self.revision)
        if "to_regclass" in sql:
            return _Scalar(self.schema)
        if "SELECT 1" in sql:
            return _Scalar(1)
        raise AssertionError("Unexpected SQL in readiness")

    def close(self):
        self.closed = True


def _prepare(monkeypatch, tmp_path, *, revision, schema):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    fake = _Database(revision, schema)
    monkeypatch.setattr(health_module, "SessionLocal", lambda: fake)
    return fake


def test_readiness_rejects_unmigrated_database(client, monkeypatch, tmp_path):
    db = _prepare(monkeypatch, tmp_path, revision=None, schema=True)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed


def test_readiness_rejects_missing_pgvector_or_core_tables(
    client, monkeypatch, tmp_path,
):
    db = _prepare(monkeypatch, tmp_path, revision=EXPECTED_HEAD, schema=False)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed


def test_readiness_requires_exact_current_schema_revision(
    client, monkeypatch, tmp_path,
):
    db = _prepare(monkeypatch, tmp_path, revision="old_revision", schema=True)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert db.closed


def test_readiness_accepts_migrated_pgvector_schema(
    client, monkeypatch, tmp_path,
):
    db = _prepare(monkeypatch, tmp_path, revision=EXPECTED_HEAD, schema=True)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ready"
    assert db.closed
