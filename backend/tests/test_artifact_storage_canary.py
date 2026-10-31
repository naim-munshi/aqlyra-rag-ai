from app.config.settings import settings
from app.services import artifact_storage_canary as canary


def test_disabled_canary_never_writes(monkeypatch):
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_CANARY_ON_STARTUP", False)
    def unexpected(**kwargs):
        raise AssertionError("Must not access storage")
    monkeypatch.setattr(canary.remote, "create_artifact", unexpected)
    assert canary.run_artifact_storage_canary() is False


def test_canary_is_owner_scoped_and_cleans_up(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "ARTIFACT_REMOTE_STORAGE_ENABLED", True)
    objects = {}
    formats = []
    def create(**kwargs):
        formats.append(kwargs["kind"])
        assert kwargs["source_document_ids"] == []
        key = str(len(formats))
        objects[(kwargs["user_id"], key)] = {"id": key, "size": 4}
        return objects[(kwargs["user_id"], key)]
    def read(*, user_id, artifact_id):
        return objects.get((user_id, artifact_id))
    def download(**kwargs):
        item = read(**kwargs)
        return (b"test", item) if item else None
    def delete(*, user_id, artifact_id):
        return objects.pop((user_id, artifact_id), None) is not None
    monkeypatch.setattr(canary.remote, "create_artifact", create)
    monkeypatch.setattr(canary.remote, "read_artifact", read)
    monkeypatch.setattr(canary.remote, "artifact_download", download)
    monkeypatch.setattr(canary.remote, "delete_artifact", delete)
    monkeypatch.setattr(canary.remote, "list_artifacts", lambda **kwargs: list(objects.values()))
    with caplog.at_level("INFO"):
        assert canary.run_artifact_storage_canary() is True
    assert formats == list(canary.FORMATS)
    assert not objects
    assert "authenticated_e2e=not_tested" in caplog.text


def test_canary_storage_failure_is_sanitized(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ARTIFACT_STORAGE_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "ARTIFACT_REMOTE_STORAGE_ENABLED", True)
    def fail(**kwargs):
        raise RuntimeError("secret-provider-message")
    monkeypatch.setattr(canary.remote, "create_artifact", fail)
    assert canary.run_artifact_storage_canary() is False
    assert "secret-provider-message" not in caplog.text
