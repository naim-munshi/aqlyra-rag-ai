"""Provider-status recovery contracts without live keys, tokens or requests."""
from pathlib import Path

import pytest

from app.llms.groq_provider import GroqLLMProvider
from app.llms.openai_provider import _classified_request_error
from app.llms.types import (
    LLMProviderPayloadTooLargeError,
    LLMProviderRateLimitError,
    LLMProviderRequestError,
)


class SyntheticUpstreamError(Exception):
    def __init__(self, status_code):
        super().__init__("never expose upstream response/private prompt")
        self.status_code = status_code


class FakeResponses:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise self.error


class FakeClient:
    def __init__(self, error):
        self.responses = FakeResponses(error)


@pytest.mark.parametrize("status_code,error_type", [
    (413, LLMProviderPayloadTooLargeError),
    (429, LLMProviderRateLimitError),
    (503, LLMProviderRequestError),
])
def test_groq_generation_preserves_actionable_status_without_leaks(status_code, error_type):
    client = FakeClient(SyntheticUpstreamError(status_code))
    provider = GroqLLMProvider(api_key="", client=client)
    with pytest.raises(error_type) as caught:
        provider.generate(
            instructions="Be helpful",
            input_text="private document contents",
        )
    assert "private document contents" not in str(caught.value)
    assert "never expose upstream" not in str(caught.value)
    assert client.responses.calls == 1


@pytest.mark.parametrize("status_code,error_type", [
    (413, LLMProviderPayloadTooLargeError),
    (429, LLMProviderRateLimitError),
])
def test_groq_stream_creation_preserves_provider_error(status_code, error_type):
    client = FakeClient(SyntheticUpstreamError(status_code))
    provider = GroqLLMProvider(api_key="", client=client)
    with pytest.raises(error_type):
        list(provider.stream(
            instructions="Be concise",
            input_text="a question",
        ))
    assert client.responses.calls == 1


def test_http_status_extracted_from_real_sdk_style_response_attribute():
    class Error(Exception):
        def __init__(self):
            self.response = type("Response", (), {"status_code": 429})()
    exc = _classified_request_error(Error(), "Groq", "generation")
    assert isinstance(exc, LLMProviderRateLimitError)


def test_413_and_429_response_handlers_precede_generic_provider_503():
    endpoint = (
        Path(__file__).parents[1] / "app" / "api" / "conversations.py"
    ).read_text()
    assert endpoint.index("except LLMProviderPayloadTooLargeError as exc:") < endpoint.index(
        "except (\n        EmbeddingError,"
    )
    assert endpoint.index("except LLMProviderRateLimitError as exc:") < endpoint.index(
        "except (\n        EmbeddingError,"
    )
    assert '"code": "provider_payload_too_large"' in endpoint
    assert '"code": "provider_rate_limited"' in endpoint
    assert '"status": 413' in endpoint and '"status": 429' in endpoint
