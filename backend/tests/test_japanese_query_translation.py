"""Experimental Japanese retrieval translation uses ONLY fake LLM responses.

Never sends actual user questions to a provider in this regression suite.
Feature remains disabled in normal production configuration.
"""
import pytest

from app.config.settings import Settings
from app.llms import LLMGeneration, LLMProviderInfo
from app.query_rewriting import LLMQueryRewriter, QueryRewriteValidationError


class FakeTranslator:
    def __init__(self, response: str):
        self.response = response
        self.instructions = ""
        self.calls = 0

    @property
    def info(self):
        return LLMProviderInfo(
            provider_name="synthetic",
            model_name="test-only",
            max_output_tokens=80,
        )

    def generate(self, *, instructions: str, input_text: str):
        self.calls += 1
        self.instructions = instructions
        return LLMGeneration(
            text=self.response, provider_name="synthetic",
            model_name="test-only",
        )


def test_production_translation_gate_defaults_off():
    # The setting default can still be overridden by a runtime environment;
    # this test checks only the declared default.
    field = Settings.model_fields["RAG_JAPANESE_TO_ENGLISH_RETRIEVAL_ENABLED"]
    assert field.default is False


def test_japanese_query_retrieval_uses_english_but_keeps_id():
    provider = FakeTranslator("ORBIT-73 experiment sample count")
    rewrite = LLMQueryRewriter(
        provider=provider, translate_japanese_to_english=True,
    )
    assert rewrite.rewrite("ORBIT-73 実験のサンプル数はいくつですか？") == (
        "ORBIT-73 experiment sample count"
    )
    assert "English retrieval query" in provider.instructions


def test_default_japanese_rewriter_does_not_translate():
    provider = FakeTranslator("ORBIT-73 サンプル数")
    rewriter = LLMQueryRewriter(provider=provider)
    assert rewriter.rewrite("ORBIT-73 のサンプル数は？") == "ORBIT-73 サンプル数"
    assert "Keep the same language" in provider.instructions


def test_english_query_does_not_trigger_japanese_translation():
    provider = FakeTranslator("ORBIT-73 sample count")
    LLMQueryRewriter(
        provider=provider, translate_japanese_to_english=True,
    ).rewrite("How many samples in ORBIT-73?")
    assert "Keep the same language" in provider.instructions


@pytest.mark.parametrize(("question", "unsafe"), [
    ("2026年に監査するのはいつですか？", "audit planned for 2025"),
    ("HM-72 は何分ごとに測定しますか？", "sensor interval"),
    ("返品ができない場合のルールは？", "policy for eligible returns"),
    ("「Aqlyra Private」を説明してください", "explain Aqlyra"),
])
def test_translation_refuses_dropped_facts_negation_or_quotes(question, unsafe):
    with pytest.raises(QueryRewriteValidationError):
        LLMQueryRewriter(
            provider=FakeTranslator(unsafe),
            translate_japanese_to_english=True,
        ).rewrite(question)


def test_japanese_negation_correct_translation_is_allowed():
    provider = FakeTranslator("cases where refund is not allowed")
    assert LLMQueryRewriter(
        provider=provider, translate_japanese_to_english=True,
    ).rewrite("返金ができない場合は？") == "cases where refund is not allowed"
