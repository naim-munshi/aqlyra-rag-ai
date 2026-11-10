"""Worker security checks, no model downloads for unit assertions."""
import os
from types import SimpleNamespace

from fastapi.testclient import TestClient
from semantic_worker import app as worker_app


class FakeEncoder:
    def encode(self, texts, mode):
        return [[1.0] + [0.0]*383 for _ in texts]


def test_worker_authentication_and_data_bounds(monkeypatch):
    monkeypatch.setenv("SEMANTIC_WORKER_TOKEN", "unit-test-token-abcdefghijklmnopqrstuvwxyz-123456")
    monkeypatch.setattr(worker_app, "get_encoder", lambda: FakeEncoder())
    # TestClient context triggers lifespan and verifies configured token
    with TestClient(worker_app.app) as client:
        payload = {"mode": "query", "texts": ["public example"]}
        assert client.post("/v1/embed", json=payload).status_code == 401
        assert client.post("/v1/embed", json=payload, headers={
            "Authorization": "Bearer wrong",
        }).status_code == 401
        response = client.post("/v1/embed", json=payload, headers={
            "Authorization": "Bearer " + os.environ["SEMANTIC_WORKER_TOKEN"],
        })
        assert response.status_code == 200
        assert response.json()["dimension"] == 384
        assert len(response.json()["vectors"][0]) == 384
        assert client.post("/v1/embed", json={
            "mode": "query", "texts": ["z" * 6001],
        }, headers={"Authorization": "Bearer " + os.environ["SEMANTIC_WORKER_TOKEN"]}).status_code == 422
        assert client.get("/openapi.json").status_code == 404


def test_embedding_worker_weights_are_pinned_to_immutable_public_revision(monkeypatch):
    from semantic_worker import model as worker_model

    seen = []
    def fake_download(**kwargs):
        seen.append(kwargs)
        return "/tmp/synthetic-public-model-placeholder"

    monkeypatch.setattr(worker_model, "hf_hub_download", fake_download)
    worker_model.download_public_model()
    assert len(worker_model.REVISION) == 40
    assert all(c in "0123456789abcdef" for c in worker_model.REVISION)
    assert {row["filename"] for row in seen} == {
        "onnx/model_int8_dim512.onnx", "tokenizer.json",
    }
    assert all(row["repo_id"] == worker_model.REPO for row in seen)
    assert all(row["revision"] == worker_model.REVISION for row in seen)
