from typing import Any

from app.llms.openai_provider import (
    OpenAILLMProvider,
)


GROQ_BASE_URL = (
    "https://api.groq.com/openai/v1"
)

DEFAULT_GROQ_MODEL = (
    "openai/gpt-oss-20b"
)


class GroqLLMProvider(
    OpenAILLMProvider
):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = (
            DEFAULT_GROQ_MODEL
        ),
        max_output_tokens: int = 800,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        client: Any | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            max_output_tokens=(
                max_output_tokens
            ),
            timeout_seconds=(
                timeout_seconds
            ),
            max_retries=max_retries,
            client=client,
            provider_name="groq",
            provider_label="Groq",
            api_key_name="GROQ_API_KEY",
            base_url=GROQ_BASE_URL,
            send_store=False,
            reasoning_effort=(
                reasoning_effort
            ),
        )
