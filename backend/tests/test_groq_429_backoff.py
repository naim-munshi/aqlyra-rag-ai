"""Quota protection regression: no real Groq credentials or requests."""
import pytest

from app.llms.groq_provider import GroqLLMProvider
from app.llms.types import LLMProviderRateLimitError


class Synthetic429(Exception):
    status_code = 429


class Responses:
    def __init__(self, fail=True):
        self.calls = 0
        self.fail = fail

    def create(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise Synthetic429("private content must never appear in errors")
        return {"output_text": "Safe normal answer", "id": "test-response"}


class FakeClient:
    def __init__(self):
        self.responses = Responses()


def test_429_cooldown_stops_repeated_calls_and_redacts_request():
    client = FakeClient()
    provider = GroqLLMProvider(api_key="", client=client)
    with pytest.raises(LLMProviderRateLimitError) as first:
        provider.generate(instructions="safe", input_text="PRIVATE-USER-DATA")
    with pytest.raises(LLMProviderRateLimitError) as second:
        provider.generate(instructions="safe", input_text="PRIVATE-USER-DATA")
    assert client.responses.calls == 1
    assert "PRIVATE-USER-DATA" not in str(first.value) + str(second.value)


def test_stream_429_is_fail_fast_during_cooldown():
    client = FakeClient()
    provider = GroqLLMProvider(api_key="", client=client)
    with pytest.raises(LLMProviderRateLimitError):
        list(provider.stream(instructions="safe", input_text="secret"))
    with pytest.raises(LLMProviderRateLimitError):
        list(provider.stream(instructions="safe", input_text="secret"))
    assert client.responses.calls == 1


def test_cooldown_expires_and_restores_work(monkeypatch):
    import app.llms.groq_provider as mod
    clock = [100.0]
    monkeypatch.setattr(mod, "monotonic", lambda: clock[0])
    client = FakeClient()
    provider = GroqLLMProvider(api_key="", client=client)
    with pytest.raises(LLMProviderRateLimitError):
        provider.generate(instructions="safe", input_text="hello")
    client.responses.fail = False
    clock[0] += 31.0
    result = provider.generate(instructions="safe", input_text="hello")
    assert result.text == "Safe normal answer"
    assert client.responses.calls == 2


def test_sdk_automatic_retry_disabled_for_configured_groq(monkeypatch):
    import app.llms.openai_provider as mod
    observed = {}

    class FakeSDK:
        def __init__(self, **kwargs):
            observed.update(kwargs)

    monkeypatch.setattr(mod, "OpenAI", FakeSDK)
    GroqLLMProvider(api_key="synthetic-only", max_retries=7)
    assert observed["max_retries"] == 0
    assert observed["base_url"].startswith("https://api.groq.com/")


def test_injected_clients_are_not_cooled_down_across_users():
    first_client = FakeClient()
    first = GroqLLMProvider(api_key="", client=first_client)
    with pytest.raises(LLMProviderRateLimitError):
        first.generate(instructions="safe", input_text="question")
    second_client = FakeClient()
    second_client.responses.fail = False
    second = GroqLLMProvider(api_key="", client=second_client)
    assert second.generate(instructions="safe", input_text="question").text == "Safe normal answer"
