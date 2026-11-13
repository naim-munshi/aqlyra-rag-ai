"""Quality-tier routing must remain private, opt-in and one-request-only.

No network, billing, provider secrets, tenant data or production mutations.
"""
import pytest

from app.config.settings import settings
from app.services import quality_model_routing as router


@pytest.mark.parametrize("message", [
    "Compare two architectures and explain the trade-offs.",
    "Analyze this failure and find the root cause.",
    "এই আর্কিটেকচার বিশ্লেষণ করে ঝুঁকি বলো",
    "দুটি পদ্ধতির তুলনা করে পরিকল্পনা দাও",
    "この設計を比較して改善計画を立てて",
])
def test_substantive_multilingual_requests_are_quality_candidates(message):
    assert router.is_complex_request(message)


@pytest.mark.parametrize("message", [
    "hi", "Hello!", "Please stop.", "What is 2+2?",
    "আজকে কেমন আছো", "ありがとう", "東京",
    "Password reset please", "What's the time?",
    "x" * 12_001,
])
def test_short_chat_and_oversized_requests_not_routed(message):
    assert not router.is_complex_request(message)


def _enable(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "synthetic-key-not-real")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "LLM_QUALITY_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "LLM_QUALITY_MAX_OUTPUT_TOKENS", 1_600)
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SECONDS", 60.0)


def test_feature_is_off_by_default_and_existing_provider_is_retained(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(settings, "LLM_QUALITY_ROUTING_ENABLED", False)
    fallback = object()
    calls = []
    monkeypatch.setattr(router, "create_configured_llm_provider", lambda: fallback)
    monkeypatch.setattr(
        router, "create_llm_provider",
        lambda **kwargs: calls.append(kwargs),
    )
    assert router.select_provider_for_normal_chat(message="Compare architectures") is fallback
    assert calls == []


def test_only_explicit_complex_requests_use_one_bounded_groq_model(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(settings, "LLM_QUALITY_ROUTING_ENABLED", True)
    calls = []
    default = object()
    chosen = object()
    monkeypatch.setattr(router, "create_configured_llm_provider", lambda: default)
    monkeypatch.setattr(
        router, "create_llm_provider",
        lambda **kwargs: calls.append(kwargs) or chosen,
    )
    assert router.select_provider_for_normal_chat(message="hi") is default
    assert router.select_provider_for_normal_chat(
        message="Analyze the root cause of the outage",
    ) is chosen
    assert len(calls) == 1
    assert calls[0]["provider_name"] == "groq"
    assert calls[0]["model_name"] == "openai/gpt-oss-120b"
    assert calls[0]["max_retries"] == 0
    assert calls[0]["max_output_tokens"] == 1_600
    assert calls[0]["reasoning_effort"] == "medium"


def test_explicit_test_provider_wins_and_no_extra_model_is_created(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(settings, "LLM_QUALITY_ROUTING_ENABLED", True)
    monkeypatch.setattr(
        router, "create_llm_provider",
        lambda **kwargs: pytest.fail("Must not create another model"),
    )
    provider = object()
    assert router.select_provider_for_normal_chat(
        message="Compare provider architectures", provider=provider,
    ) is provider


def test_allowlist_denies_unknown_model_and_non_groq_provider(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(settings, "LLM_QUALITY_ROUTING_ENABLED", True)
    base = object()
    monkeypatch.setattr(router, "create_configured_llm_provider", lambda: base)
    monkeypatch.setattr(
        router, "create_llm_provider",
        lambda **kwargs: pytest.fail("Unsupported model should never be called"),
    )
    monkeypatch.setattr(settings, "LLM_QUALITY_MODEL", "unknown/expensive-model")
    assert router.select_provider_for_normal_chat(message="Analyze architecture") is base
    monkeypatch.setattr(settings, "LLM_QUALITY_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    assert router.select_provider_for_normal_chat(message="Analyze architecture") is base


def test_matching_default_model_avoids_recreating_same_provider(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(settings, "LLM_QUALITY_ROUTING_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-120b")
    base = object()
    monkeypatch.setattr(router, "create_configured_llm_provider", lambda: base)
    monkeypatch.setattr(
        router, "create_llm_provider",
        lambda **kwargs: pytest.fail("Same model must not create duplicate provider"),
    )
    assert router.select_provider_for_normal_chat(message="Analyze this") is base
