"""Offline regression: connection-only readiness must not claim RAG is ready.

No production secrets, network calls or schema mutations.
"""
from app.config.settings import settings
from app.api.v1 import health as health_module


EXPECTED_HEAD = "f6a9b2c4d8e1"


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Database:
    def __init__(
        self, revision, schema, full_schema=True, fit_columns=True,
        refresh_sessions_ready=True, agent_tables_ready=True,
    ):
        self.revision = revision
        self.schema = schema
        self.full_schema = full_schema
        self.fit_columns = fit_columns
        self.refresh_sessions_ready = refresh_sessions_ready
        self.agent_tables_ready = agent_tables_ready
        self.closed = False

    def execute(self, query):
        sql = str(query)
        if "alembic_version" in sql:
            return _Scalar(self.revision)
        if all(name in sql for name in (
            "agent_runs", "agent_steps", "agent_daily_usage",
        )):
            return _Scalar(self.agent_tables_ready)
        if "refresh_sessions" in sql:
            return _Scalar(self.refresh_sessions_ready)
        if "information_schema.columns" in sql:
            return _Scalar(self.fit_columns)
        if "study_cases" in sql:
            return _Scalar(self.full_schema)
        if "to_regclass" in sql:
            return _Scalar(self.schema)
        if "SELECT 1" in sql:
            return _Scalar(1)
        raise AssertionError("Unexpected SQL in readiness")

    def close(self):
        self.closed = True


def _prepare(
    monkeypatch, tmp_path, *, revision, schema, full_schema=True,
    fit_columns=True, refresh_sessions_ready=True, agent_tables_ready=True,
):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    fake = _Database(
        revision, schema, full_schema=full_schema, fit_columns=fit_columns,
        refresh_sessions_ready=refresh_sessions_ready,
        agent_tables_ready=agent_tables_ready,
    )
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


def test_readiness_rejects_pre_refresh_full_head_even_with_all_tables(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision="d4ec2f9b7860",
        schema=True, full_schema=True,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed

def test_readiness_rejects_refresh_head_with_missing_study_table(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision=EXPECTED_HEAD,
        schema=True, full_schema=False,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed


def test_readiness_rejects_study_fit_head_before_refresh_sessions(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision="0bd6703bf8a4",
        schema=True, full_schema=True, fit_columns=True,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed

def test_readiness_rejects_missing_study_fit_columns(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision=EXPECTED_HEAD,
        schema=True, full_schema=True, fit_columns=False,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed


def test_readiness_rejects_refresh_head_without_study_tables(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision=EXPECTED_HEAD,
        schema=True, full_schema=False, fit_columns=True,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert db.closed


def test_readiness_rejects_agent_head_with_missing_agent_harness_tables(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision=EXPECTED_HEAD,
        schema=True, full_schema=True, fit_columns=True,
        agent_tables_ready=False,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed


def test_readiness_still_rejects_unreviewed_future_revision(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision="unreviewed_future_head",
        schema=True, full_schema=True,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert db.closed



def test_render_git_sha_readiness_metadata_is_validated(
    client, monkeypatch, tmp_path,
):
    expected = "a" * 40
    _prepare(monkeypatch, tmp_path, revision=EXPECTED_HEAD, schema=True)
    monkeypatch.setenv("RENDER_GIT_COMMIT", expected)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["deployment_git_sha"] == expected
    # No new metadata may affect the documented liveness response contract.
    assert "deployment_git_sha" not in client.get("/api/v1/health").json()


def test_bad_render_git_sha_does_not_leak_environment_text(
    client, monkeypatch, tmp_path,
):
    _prepare(monkeypatch, tmp_path, revision=EXPECTED_HEAD, schema=True)
    bad_value = "PRIVATE-SECRET-OR-OTHER-UNTRUSTED-ENVIRONMENT-DATA"
    monkeypatch.setenv("RENDER_GIT_COMMIT", bad_value)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert "deployment_git_sha" not in response.json()
    assert bad_value not in response.text

def test_readiness_accepts_reviewed_refresh_session_head(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision="a1f8c6d2e904",
        schema=True, full_schema=True, fit_columns=True,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ready"
    assert db.closed


def test_readiness_rejects_refresh_session_head_with_missing_schema(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision=EXPECTED_HEAD,
        schema=True, full_schema=True, fit_columns=True,
        refresh_sessions_ready=False,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed

def test_readiness_rejects_refresh_session_head_with_missing_study_fit_columns(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision="a1f8c6d2e904",
        schema=True, full_schema=True, fit_columns=False,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed


def test_readiness_rejects_refresh_session_head_without_full_schema(
    client, monkeypatch, tmp_path,
):
    db = _prepare(
        monkeypatch, tmp_path, revision="a1f8c6d2e904",
        schema=True, full_schema=False, fit_columns=True,
    )
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert db.closed
