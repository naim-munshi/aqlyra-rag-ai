from pathlib import Path


def test_production_env_example_has_individual_storage_settings():
    template = Path(__file__).resolve().parents[1] / ".env.production.example"
    lines = template.read_text(encoding="utf-8").splitlines()
    values = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assert "=" in line
        key, value = line.split("=", 1)
        assert key not in values
        values[key] = value
    for key in (
        "LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED",
        "PRIVATE_OBJECT_STORAGE_ENABLED",
        "ARTIFACT_REMOTE_STORAGE_ENABLED",
        "CLOUD_UPLOAD_PUBLIC_ENABLED",
    ):
        assert values[key] == "false"
