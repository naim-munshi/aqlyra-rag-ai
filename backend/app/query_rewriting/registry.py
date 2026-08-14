from app.config.settings import settings
from app.llms import (
    LLMError,
    create_llm_provider,
)
from app.query_rewriting.identity import (
    IdentityQueryRewriter,
)
from app.query_rewriting.llm_rewriter import (
    LLMQueryRewriter,
)
from app.query_rewriting.types import (
    QueryRewriter,
    QueryRewriteValidationError,
)


SUPPORTED_QUERY_REWRITER_PROVIDERS = frozenset(
    {
        "identity",
        "llm",
    }
)


def create_configured_query_rewriter(
) -> QueryRewriter:
    provider_name = (
        settings.QUERY_REWRITER_PROVIDER
        .strip()
        .lower()
    )

    if provider_name == "identity":
        return IdentityQueryRewriter()

    if provider_name != "llm":
        raise QueryRewriteValidationError(
            "Unsupported query rewriter provider: "
            f"{provider_name}"
        )

    if settings.LLM_PROVIDER not in {
        "groq",
        "openai",
    }:
        raise QueryRewriteValidationError(
            "LLM query rewriting requires "
            "Groq or OpenAI"
        )

    api_key = (
        settings.GROQ_API_KEY
        if settings.LLM_PROVIDER == "groq"
        else settings.OPENAI_API_KEY
    )

    try:
        provider = create_llm_provider(
            provider_name=settings.LLM_PROVIDER,
            model_name=settings.LLM_MODEL,
            api_key=api_key,
            max_output_tokens=(
                settings
                .QUERY_REWRITER_MAX_OUTPUT_TOKENS
            ),
            timeout_seconds=(
                settings.LLM_TIMEOUT_SECONDS
            ),
            max_retries=(
                settings.LLM_MAX_RETRIES
            ),
            reasoning_effort=(
                settings
                .QUERY_REWRITER_REASONING_EFFORT
            ),
        )

    except LLMError as exc:
        raise QueryRewriteValidationError(
            "Could not configure query rewriter"
        ) from exc

    return LLMQueryRewriter(
        provider=provider,
        max_chars=(
            settings.QUERY_REWRITER_MAX_CHARS
        ),
    )
