import pytest

from app.llms import (
    LLMGeneration,
    LLMProviderInfo,
    LLMProviderRequestError,
)
from app.query_rewriting import (
    IdentityQueryRewriter,
    LLMQueryRewriter,
    QueryRewriteError,
    QueryRewriteValidationError,
)


class FakeLLMProvider:
    def __init__(
        self,
        response: str,
    ) -> None:
        self.response = response
        self.last_instructions = ""
        self.last_input = ""

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="fake",
            model_name="fake-model",
            max_output_tokens=128,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        self.last_instructions = instructions
        self.last_input = input_text

        return LLMGeneration(
            text=self.response,
            provider_name="fake",
            model_name="fake-model",
        )


class FailingLLMProvider(
    FakeLLMProvider
):
    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        raise LLMProviderRequestError(
            "provider unavailable"
        )


def test_identity_rewriter_normalizes_query() -> None:
    rewriter = IdentityQueryRewriter()

    assert rewriter.rewrite(
        "  annual   security review  "
    ) == "annual security review"


def test_llm_rewriter_returns_clean_query() -> None:
    provider = FakeLLMProvider(
        "yearly security assessment scheduled month"
    )

    rewriter = LLMQueryRewriter(
        provider=provider
    )

    result = rewriter.rewrite(
        "Which month is the yearly "
        "security assessment scheduled?"
    )

    assert result == (
        "yearly security assessment scheduled month"
    )

    assert provider.last_input == (
        "Which month is the yearly "
        "security assessment scheduled?"
    )


@pytest.mark.parametrize(
    ("original", "rewritten"),
    (
        (
            "What is the code ZX-41-LANTERN?",
            "emergency credential ZX-41-LANTERN",
        ),
        (
            "How many samples in ORBIT-73?",
            "ORBIT-73 experiment sample count",
        ),
        (
            "Does backup begin at 02:30 UTC?",
            "backup schedule 02:30 UTC",
        ),
        (
            "What happens above 2.5 percent?",
            "error rate above 2.5 percent",
        ),
    ),
)
def test_rewriter_preserves_protected_tokens(
    original: str,
    rewritten: str,
) -> None:
    rewriter = LLMQueryRewriter(
        provider=FakeLLMProvider(
            rewritten
        )
    )

    assert rewriter.rewrite(
        original
    ) == rewritten


def test_rewriter_rejects_removed_identifier() -> None:
    rewriter = LLMQueryRewriter(
        provider=FakeLLMProvider(
            "emergency credential reference"
        )
    )

    with pytest.raises(
        QueryRewriteValidationError
    ):
        rewriter.rewrite(
            "What is code ZX-41-LANTERN?"
        )


def test_rewriter_rejects_substring_token_change() -> None:
    rewriter = LLMQueryRewriter(
        provider=FakeLLMProvider(
            "item count 173"
        )
    )

    with pytest.raises(
        QueryRewriteValidationError
    ):
        rewriter.rewrite(
            "How many items are in batch 73?"
        )


def test_rewriter_rejects_added_numeric_fact() -> None:
    rewriter = LLMQueryRewriter(
        provider=FakeLLMProvider(
            "security review scheduled month 10"
        )
    )

    with pytest.raises(
        QueryRewriteValidationError
    ):
        rewriter.rewrite(
            "Which month is the security review scheduled?"
        )


def test_rewriter_rejects_empty_response() -> None:
    rewriter = LLMQueryRewriter(
        provider=FakeLLMProvider(
            "   "
        )
    )

    with pytest.raises(
        QueryRewriteValidationError
    ):
        rewriter.rewrite(
            "security review month"
        )


def test_rewriter_rejects_excessive_length() -> None:
    rewriter = LLMQueryRewriter(
        provider=FakeLLMProvider(
            "x" * 101
        ),
        max_chars=100,
    )

    with pytest.raises(
        QueryRewriteValidationError
    ):
        rewriter.rewrite(
            "security review"
        )


def test_rewriter_wraps_provider_failure() -> None:
    rewriter = LLMQueryRewriter(
        provider=FailingLLMProvider(
            ""
        )
    )

    with pytest.raises(
        QueryRewriteError
    ):
        rewriter.rewrite(
            "security review"
        )
