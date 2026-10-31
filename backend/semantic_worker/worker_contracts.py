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
