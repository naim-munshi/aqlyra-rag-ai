"""Safe zero-cost staging profile must not auto-migrate a remote DB."""
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "backend" / "docker-entrypoint.sh"
BLUEPRINT = ROOT / "deploy" / "render-free-staging.yaml"


def test_manual_startup_mode_never_touches_db():
    run = subprocess.run(
        ["sh", str(ENTRY), "sh", "-c", "printf manual-safe"],
        env={**os.environ, "DATABASE_MIGRATION_MODE": "manual"},
        capture_output=True, text=True, check=True, timeout=5,
    )
    assert run.stdout.endswith("manual-safe")
    assert "Applying Alembic" not in run.stdout
    assert "Preparing pgvector" not in run.stdout


def test_invalid_migration_mode_fails_closed():
    run = subprocess.run(
        ["sh", str(ENTRY), "true"],
        env={**os.environ, "DATABASE_MIGRATION_MODE": "unexpected"},
        capture_output=True, text=True, timeout=5,
    )
    assert run.returncode != 0


def test_free_staging_blueprint_has_no_autodeploy_or_enabled_upload():
    data = yaml.safe_load(BLUEPRINT.read_text())
    assert data["previews"]["generation"] == "off"
    assert len(data["services"]) == 1
    service = data["services"][0]
    assert service["plan"] == "free"
    assert service["runtime"] == "docker"
    assert service["branch"] == "release/core-without-study-abroad-20261027"
    assert service["autoDeployTrigger"] == "off"
    envs = {entry["key"]: entry for entry in service["envVars"]}
    for key in (
        "PRIVATE_OBJECT_STORAGE_ENABLED",
        "CLOUD_UPLOAD_PUBLIC_ENABLED",
        "BROWSER_AGENT_ENABLED",
    ):
        assert envs[key]["value"] == "false"
    assert envs["DATABASE_MIGRATION_MODE"]["value"] == "manual"
    for key in ("DATABASE_URL", "SECRET_KEY", "REDIS_URL", "RESEND_API_KEY", "HF_TOKEN"):
        assert envs[key] == {"key": key, "sync": False}
    assert "databases" not in data
    assert "keyvalue" not in str(data)
