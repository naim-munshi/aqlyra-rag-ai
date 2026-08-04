from typing import Any

from app.config.settings import settings
from app.llms.deterministic_provider import (
    DEFAULT_DETERMINISTIC_RESPONSE,
    DeterministicLLMProvider,
)
from app.llms.openai_provider import (
    OpenAILLMProvider,
)
from app.llms.types import (
    LLMProvider,
    LLMValidationError,
)


SUPPORTED_LLM_PROVIDERS = frozenset(
    {
        "deterministic",
        "openai",
    }
)


def create_llm_provider(
    *,
    provider_name: str,
    model_name: str = "gpt-5",
    api_key: str = "",
    max_output_tokens: int = 800,
    timeout_seconds: float = 60.0,
    max_retries: int = 2,
    deterministic_response: str = (
        DEFAULT_DETERMINISTIC_RESPONSE
    ),
    client: Any | None = None,
) -> LLMProvider:
    normalized_provider = (
        provider_name.strip().lower()
    )

    if normalized_provider == (
        "deterministic"
    ):
        return DeterministicLLMProvider(
            response_text=(
                deterministic_response
            ),
            max_output_tokens=(
                max_output_tokens
            ),
        )

    if normalized_provider == "openai":
        return OpenAILLMProvider(
            api_key=api_key,
            model=model_name,
            max_output_tokens=(
                max_output_tokens
            ),
            timeout_seconds=(
                timeout_seconds
            ),
            max_retries=max_retries,
            client=client,
        )

    supported = ", ".join(
        sorted(
            SUPPORTED_LLM_PROVIDERS
        )
    )

    raise LLMValidationError(
        "Unsupported LLM provider "
        f"'{provider_name}'. "
        f"Supported providers: {supported}"
    )


def create_configured_llm_provider(
) -> LLMProvider:
    return create_llm_provider(
        provider_name=(
            settings.LLM_PROVIDER
        ),
        model_name=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        max_output_tokens=(
            settings
            .LLM_MAX_OUTPUT_TOKENS
        ),
        timeout_seconds=(
            settings.LLM_TIMEOUT_SECONDS
        ),
        max_retries=(
            settings.LLM_MAX_RETRIES
        ),
    )
