"""Real 502/cold-start resilience without changing the 384-d vector schema."""
import httpx
import pytest

from app.embeddings.remote_semantic_provider import (
    MODEL, RemoteSemanticEmbeddingProvider, _shared_circuit,
)
from app.embeddings.types import EmbeddingProviderRequestError, EmbeddingValidationError


URL = "https://aqlyra-semantic-worker.onrender.com"
TOKEN = "safe-unique-test-semantic-token-over-32-characters"
VECTOR = [0.0, 3.0, 4.0] + [0.0] * 381


def provider(client):
    return RemoteSemanticEmbeddingProvider(
        base_url=URL, api_token=TOKEN, client=client,
    )


def good_response():
    return httpx.Response(200, json={
        "model": MODEL, "dimension": 384, "vectors": [VECTOR],
    })


def test_transient_502_recovers_without_reembedding_or_fabricating(monkeypatch):
    delays, calls = [], []
    monkeypatch.setattr(
        "app.embeddings.remote_semantic_provider.time.sleep",
        lambda seconds: delays.append(seconds),
    )

    def handle(request):
        assert request.url.path == "/v1/embed"
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        calls.append(request)
        return httpx.Response(502) if len(calls) == 1 else good_response()

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        actual = provider(client).embed_query("বাংলাদেশ সম্পর্কে বলো")
    assert len(calls) == 2
    assert delays == [0.5]
    assert len(actual) == 384
    assert abs(sum(x * x for x in actual) - 1) < 1e-5


def test_circuit_opens_after_three_failed_calls_without_retry_storm(monkeypatch):
    attempts = []
    monkeypatch.setattr(
        "app.embeddings.remote_semantic_provider.time.sleep",
        lambda _: None,
    )

    def handle(_request):
        attempts.append(1)
        return httpx.Response(502, text="internal private provider details")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        p = provider(client)
        for _ in range(3):
            with pytest.raises(EmbeddingProviderRequestError) as exc:
                p.embed_query("sensitive document text")
            assert "sensitive document text" not in str(exc.value)
            assert "private provider details" not in str(exc.value)
        assert len(attempts) == 6
        with pytest.raises(EmbeddingProviderRequestError):
            p.embed_query("no more network")
        assert len(attempts) == 6, "open circuit must fail before network"


def test_non_retryable_auth_failure_stops_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.embeddings.remote_semantic_provider.time.sleep",
        lambda _: pytest.fail("should not retry 401"),
    )

    def handle(request):
        calls.append(request)
        return httpx.Response(401, text="private-secret")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        p = provider(client)
        with pytest.raises(EmbeddingProviderRequestError) as exc:
            p.embed_query("test")
        assert len(calls) == 1
        assert p._circuit.consecutive_failures == 0
        assert "private-secret" not in str(exc.value)


def test_wrong_model_and_dimension_remain_fail_closed_without_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.embeddings.remote_semantic_provider.time.sleep",
        lambda _: pytest.fail("metadata mismatch must not retry"),
    )

    def handle(req):
        calls.append(req)
        return httpx.Response(200, json={
            "model": "wrong-model", "dimension": 384, "vectors": [VECTOR],
        })

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(EmbeddingValidationError):
            provider(client).embed_query("test")
    assert len(calls) == 1


def test_transport_timeout_retries_once_then_fails_closed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.embeddings.remote_semantic_provider.time.sleep",
        lambda _: None,
    )

    def handle(request):
        calls.append(request)
        raise httpx.ConnectTimeout("Synthetic connection timeout")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(EmbeddingProviderRequestError):
            provider(client).embed_query("test")
        assert len(calls) == 2


def test_circuit_registry_reuses_process_state_without_plaintext_secrets():
    token = "other-safe-synthetic-test-token-000000000"
    first = _shared_circuit(URL, token)
    second = _shared_circuit(URL, token)
    different = _shared_circuit(URL, token + "x")
    assert first is second
    assert first is not different
    from app.embeddings.remote_semantic_provider import _BREAKER_REGISTRY
    assert token not in str(tuple(_BREAKER_REGISTRY.keys()))


def test_production_embedding_http_pool_is_shared_without_sharing_credentials():
    first = RemoteSemanticEmbeddingProvider(base_url=URL, api_token=TOKEN)
    second = RemoteSemanticEmbeddingProvider(base_url=URL, api_token=TOKEN + "z")
    assert first._client is second._client
    assert first._circuit is not second._circuit
    assert first._client.follow_redirects is False


@pytest.mark.parametrize("invalid", [
    "1.0", None, True, {"value": 1}, 10 ** 1000,
    float("nan"), float("inf"),
])
def test_malformed_semantic_json_never_yields_a_vector(invalid):
    import json

    def handle(_request):
        body = {
            "model": MODEL, "dimension": 384,
            "vectors": [[invalid] + [1.0] * 383],
        }
        # httpx's strict JSON serializer rejects NaN/Infinity before
        # the application ever receives the mocked provider payload.
        # Deliberately inject the malformed raw response to exercise
        # our *client* validation, not the mock response constructor.
        return httpx.Response(
            200,
            content=json.dumps(body, allow_nan=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(EmbeddingValidationError):
            provider(client).embed_query("private text")
    # Invalid external vectors cannot be used as deterministic substitutes.


def test_large_finite_semantic_vector_is_normalized_without_overflow():
    import math
    def handle(_request):
        return httpx.Response(200, json={
            "model": MODEL, "dimension": 384,
            "vectors": [[1e308] * 384],
        })

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        normalized = provider(client).embed_query("test")
    assert len(normalized) == 384
    assert all(math.isfinite(value) and value > 0 for value in normalized)
    assert math.fsum(value * value for value in normalized) == pytest.approx(1.0)


def test_zero_semantic_vector_fails_closed():
    def handle(_request):
        return httpx.Response(200, json={
            "model": MODEL, "dimension": 384,
            "vectors": [[0.0] * 384],
        })

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(EmbeddingValidationError, match="magnitude"):
            provider(client).embed_query("test")
