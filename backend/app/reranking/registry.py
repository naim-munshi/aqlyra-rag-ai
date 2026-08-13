from app.config.settings import settings
from app.llms import (
    LLMError,
    create_llm_provider,
)
from app.reranking.identity_provider import (
    IdentityReranker,
)
from app.reranking.llm_provider import (
    LLMReranker,
    RERANKER_TEXT_FORMAT,
)
from app.reranking.types import (
    RerankerProvider,
    RerankerValidationError,
)


SUPPORTED_RERANKER_PROVIDERS = frozenset(
    {
        "identity",
        "llm",
    }
)


def create_configured_reranker(
) -> RerankerProvider:
    provider_name = (
        settings.RERANKER_PROVIDER
        .strip()
        .lower()
    )

    if provider_name == "identity":
        return IdentityReranker()

    if provider_name != "llm":
        raise RerankerValidationError(
            "Unsupported reranker provider: "
            f"{provider_name}"
        )

    if settings.LLM_PROVIDER not in {
        "groq",
        "openai",
    }:
        raise RerankerValidationError(
            "LLM reranking requires Groq "
            "or OpenAI"
        )

    api_key = (
        settings.GROQ_API_KEY
        if settings.LLM_PROVIDER == "groq"
        else settings.OPENAI_API_KEY
    )

    try:
        llm_provider = create_llm_provider(
            provider_name=(
                settings.LLM_PROVIDER
            ),
            model_name=settings.LLM_MODEL,
            api_key=api_key,
            max_output_tokens=(
                settings
                .RERANKER_MAX_OUTPUT_TOKENS
            ),
            timeout_seconds=(
                settings
                .LLM_TIMEOUT_SECONDS
            ),
            max_retries=(
                settings.LLM_MAX_RETRIES
            ),
            reasoning_effort=(
                settings
                .RERANKER_REASONING_EFFORT
            ),
            text_format=(
                RERANKER_TEXT_FORMAT
            ),
        )

    except LLMError as exc:
        raise RerankerValidationError(
            "Could not configure LLM reranker"
        ) from exc

    return LLMReranker(
        provider=llm_provider,
        max_candidate_chars=(
            settings
            .RERANKER_MAX_CANDIDATE_CHARS
        ),
    )
