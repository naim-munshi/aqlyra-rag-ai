"""Bounded bulk recovery controls. No external provider or production data."""
from app.config.settings import settings
import app.services.knowledge_semantic_backfill as mod


def _campaign_on(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "remote_onnx")
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_ALL_VERIFIED_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_RECOVERY_CAMPAIGN_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID", "")
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_MAX_CHUNKS", 8)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_MAX_BATCHES", 8)
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)


def test_campaign_off_by_default_never_touches_provider(monkeypatch):
    _campaign_on(monkeypatch)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_RECOVERY_CAMPAIGN_ENABLED", False)
    monkeypatch.setattr(mod, "backfill_ready_semantic_embeddings",
                        lambda **_: (_ for _ in ()).throw(AssertionError("unexpected provider call")))
    assert mod.run_verified_semantic_recovery_campaign(db=None) == 0


def test_campaign_requires_separate_verified_scan_opt_in(monkeypatch):
    _campaign_on(monkeypatch)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_ALL_VERIFIED_ENABLED", False)
    monkeypatch.setattr(mod, "backfill_ready_semantic_embeddings",
                        lambda **_: (_ for _ in ()).throw(AssertionError("unexpected provider call")))
    assert mod.run_verified_semantic_recovery_campaign(db=None) == 0


def test_campaign_rejects_target_conflict(monkeypatch):
    _campaign_on(monkeypatch)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_TARGET_DOCUMENT_ID", "document-id")
    monkeypatch.setattr(mod, "backfill_ready_semantic_embeddings",
                        lambda **_: (_ for _ in ()).throw(AssertionError("unexpected provider call")))
    assert mod.run_verified_semantic_recovery_campaign(db=None) == 0


def test_campaign_resumes_three_docs_per_pass_and_stops_after_empty(monkeypatch):
    _campaign_on(monkeypatch)
    sizes = iter([64, 53, 0])
    calls = []

    def fake_pass(*, db, limit, progress):
        assert limit == 3
        created = next(sizes)
        calls.append(created)
        progress.created_chunks = created
        return 3 if created else 0

    monkeypatch.setattr(mod, "backfill_ready_semantic_embeddings", fake_pass)
    assert mod.run_verified_semantic_recovery_campaign(db=None) == 117
    assert calls == [64, 53, 0]


def test_campaign_provider_failure_stops_without_retry(monkeypatch):
    _campaign_on(monkeypatch)
    calls = []

    def fake_pass(*, db, limit, progress):
        calls.append(True)
        progress.created_chunks = 8
        progress.failed = True
        return 1

    monkeypatch.setattr(mod, "backfill_ready_semantic_embeddings", fake_pass)
    assert mod.run_verified_semantic_recovery_campaign(db=None) == 8
    assert len(calls) == 1


def test_campaign_never_exceeds_1024_chunk_global_budget(monkeypatch):
    _campaign_on(monkeypatch)
    calls = []

    def fake_pass(*, db, limit, progress):
        calls.append(True)
        progress.created_chunks = 64
        return 3

    monkeypatch.setattr(mod, "backfill_ready_semantic_embeddings", fake_pass)
    assert mod.run_verified_semantic_recovery_campaign(db=None) == 1024
    assert len(calls) == 16


def test_campaign_rejects_oversized_per_pass_budget(monkeypatch):
    _campaign_on(monkeypatch)
    monkeypatch.setattr(settings, "KNOWLEDGE_SEMANTIC_BACKFILL_MAX_CHUNKS", 24)
    import pytest
    with pytest.raises(ValueError, match="64"):
        mod.run_verified_semantic_recovery_campaign(db=None)
