"""Remote semantic provider fail-closed security and vector shape contracts."""
import math

import httpx
import pytest

from app.embeddings.remote_semantic_provider import (
    RemoteSemanticEmbeddingProvider,
)
from app.embeddings.types import EmbeddingProviderRequestError, EmbeddingValidationError
from app.embeddings.registry import create_embedding_provider

BASE = "https://aqlyra-semantic-worker.onrender.com"
TOKEN = "unit-test-token-not-production-value-000000"


def test_remote_onnx_vectors_and_query_passage_modes():
    modes = []
    def handler(req):
        assert req.url.host == "aqlyra-semantic-worker.onrender.com"
        assert req.url.path == "/v1/embed"
        assert req.headers["Authorization"] == "Bearer " + TOKEN
        body = __import__("json").loads(req.content)
        modes.append(body["mode"])
        return httpx.Response(200, json={
            "model": "multilingual-e5-small-int8-v1",
            "dimension": 384,
            "vectors": [[0.0, 3.0, 4.0] + [0.0]*381 for _ in body["texts"]],
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        p = create_embedding_provider(
            provider_name="remote_onnx", dimension=384,
            remote_url=BASE, remote_token=TOKEN, client=client,
        )
        docs = p.embed_documents(["English text", "বাংলা লেখা"])
        q = p.embed_query("日本語")
    assert modes == ["passage", "query"]
    assert p.info.provider_name == "remote_onnx"
    assert len(docs) == 2 and len(q) == 384
    assert math.isclose(sum(v*v for v in q), 1.0, abs_tol=0.0001)


@pytest.mark.parametrize("url", [
    "http://aqlyra-semantic-worker.onrender.com",
    "https://localhost",
    "https://127.0.0.1",
    "https://internal.local",
    "https://evil.com",
    "https://abc.onrender.com@evil.com",
    "https://aqlyra-semantic-worker.onrender.com/anything",
])
def test_remote_requires_expected_https_host(url):
    with pytest.raises(EmbeddingValidationError):
        RemoteSemanticEmbeddingProvider(base_url=url, api_token=TOKEN)


def test_remote_rejects_wrong_model_and_fabricated_dimensions():
    def handler(req):
        return httpx.Response(200, json={
            "model": "wrong", "dimension": 384,
            "vectors": [[1.0] * 384],
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        p = RemoteSemanticEmbeddingProvider(
            base_url=BASE, api_token=TOKEN, client=client,
        )
        with pytest.raises(EmbeddingValidationError):
            p.embed_query("Test")


def test_remote_rejects_error_without_leaking_response_body():
    with httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(503, text="secret error"),
    )) as client:
        p = RemoteSemanticEmbeddingProvider(
            base_url=BASE, api_token=TOKEN, client=client,
        )
        with pytest.raises(EmbeddingProviderRequestError) as exc:
            p.embed_query("private user content")
        assert "secret" not in str(exc.value)
        assert "private user content" not in str(exc.value)


def test_remote_rejects_short_token():
    with pytest.raises(EmbeddingValidationError):
        RemoteSemanticEmbeddingProvider(base_url=BASE, api_token="short")
