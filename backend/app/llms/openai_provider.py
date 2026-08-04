from typing import Any

from openai import OpenAI

from app.llms.types import (
    LLMGeneration,
    LLMProviderInfo,
    LLMProviderRequestError,
    LLMProviderResponseError,
    LLMValidationError,
)


def _read_value(
    value: Any,
    name: str,
    default: Any = None,
) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)

    return getattr(
        value,
        name,
        default,
    )


def _optional_integer(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _extract_response_text(
    response: Any,
) -> str:
    output_text = _read_value(
        response,
        "output_text",
        "",
    )

    if isinstance(output_text, str):
        cleaned_output = output_text.strip()

        if cleaned_output:
            return cleaned_output

    output_items = _read_value(
        response,
        "output",
        (),
    )

    for item in output_items or ():
        content_parts = _read_value(
            item,
            "content",
            (),
        )

        for part in content_parts or ():
            part_type = _read_value(
                part,
                "type",
                "",
            )

            if part_type == "output_text":
                text = _read_value(
                    part,
                    "text",
                    "",
                )

                if isinstance(text, str):
                    cleaned_text = text.strip()

                    if cleaned_text:
                        return cleaned_text

            if part_type == "refusal":
                refusal = _read_value(
                    part,
                    "refusal",
                    "",
                )

                if isinstance(refusal, str):
                    cleaned_refusal = (
                        refusal.strip()
                    )

                    if cleaned_refusal:
                        return cleaned_refusal

    raise LLMProviderResponseError(
        "OpenAI returned no usable text output"
    )


class OpenAILLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5",
        max_output_tokens: int = 800,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        cleaned_model = model.strip()

        if not cleaned_model:
            raise LLMValidationError(
                "OpenAI model cannot be empty"
            )

        if max_output_tokens < 1:
            raise LLMValidationError(
                "max_output_tokens must be positive"
            )

        if timeout_seconds <= 0:
            raise LLMValidationError(
                "timeout_seconds must be positive"
            )

        if max_retries < 0:
            raise LLMValidationError(
                "max_retries cannot be negative"
            )

        cleaned_key = api_key.strip()

        if client is None and not cleaned_key:
            raise LLMValidationError(
                "OPENAI_API_KEY is required "
                "for the OpenAI LLM provider"
            )

        self._info = LLMProviderInfo(
            provider_name="openai",
            model_name=cleaned_model,
            max_output_tokens=(
                max_output_tokens
            ),
        )

        self._client = (
            client
            if client is not None
            else OpenAI(
                api_key=cleaned_key,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        )

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        cleaned_instructions = (
            instructions.strip()
        )

        cleaned_input = input_text.strip()

        if not cleaned_instructions:
            raise LLMValidationError(
                "LLM instructions cannot be empty"
            )

        if not cleaned_input:
            raise LLMValidationError(
                "LLM input cannot be empty"
            )

        try:
            response = (
                self._client.responses.create(
                    model=self.info.model_name,
                    instructions=(
                        cleaned_instructions
                    ),
                    input=cleaned_input,
                    max_output_tokens=(
                        self.info.max_output_tokens
                    ),
                    store=False,
                )
            )
        except Exception as exc:
            raise LLMProviderRequestError(
                "OpenAI response generation failed"
            ) from exc

        text = _extract_response_text(
            response
        )

        usage = _read_value(
            response,
            "usage",
        )

        response_id_value = _read_value(
            response,
            "id",
        )

        response_id = (
            str(response_id_value)
            if response_id_value is not None
            else None
        )

        return LLMGeneration(
            text=text,
            provider_name=(
                self.info.provider_name
            ),
            model_name=self.info.model_name,
            response_id=response_id,
            input_tokens=_optional_integer(
                _read_value(
                    usage,
                    "input_tokens",
                )
            ),
            output_tokens=_optional_integer(
                _read_value(
                    usage,
                    "output_tokens",
                )
            ),
            total_tokens=_optional_integer(
                _read_value(
                    usage,
                    "total_tokens",
                )
            ),
        )
