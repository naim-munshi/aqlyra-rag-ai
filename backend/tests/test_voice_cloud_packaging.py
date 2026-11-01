"""The LiveKit CLI must deploy the voice Dockerfile, never the FastAPI Dockerfile."""

import importlib.util
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_livekit_context.py"
_spec = importlib.util.spec_from_file_location("voice_package", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_package = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_package)


def test_cloud_context_uses_voice_dockerfile_and_excludes_secrets(tmp_path):
    source = tmp_path / "backend"
    (source / "app" / "voice").mkdir(parents=True)
    (source / "Dockerfile.voice").write_text("FROM python:3.13-slim\n# voice-only\n")
    (source / "Dockerfile").write_text("FROM nginx\n# HTTP API\n")
    (source / "requirements.txt").write_text("pytest\n")
    (source / "requirements-voice.txt").write_text("-r requirements.txt\n")
    (source / ".dockerignore").write_text(".env\n")
    (source / "app" / "voice" / "worker.py").write_text("# agent\n")
    (source / ".env").write_text("SECRET_KEY=do-not-package\n")
    (source / "uploads").mkdir()
    (source / "uploads" / "private.txt").write_text("private\n")

    target = tmp_path / "voice-build"
    _package.prepare_voice_context(target, source=source)

    assert "voice-only" in (target / "Dockerfile").read_text()
    assert not (target / "Dockerfile.voice").exists()
    assert not (target / ".env").exists()
    assert not (target / "uploads").exists()
    assert (target / "app" / "voice" / "worker.py").exists()


def test_rejects_packaging_into_the_source_tree(tmp_path):
    with pytest.raises(ValueError):
        _package.prepare_voice_context(tmp_path / "backend" / "build", source=tmp_path / "backend")


def test_rejects_overwriting_existing_output(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    with pytest.raises(FileExistsError):
        _package.prepare_voice_context(target, source=tmp_path / "backend")
