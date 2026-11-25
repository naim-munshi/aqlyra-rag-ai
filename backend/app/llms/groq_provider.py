"""Groq provider: avoid quota-storm SDK retries and fail fast during 429 cooldown.

A best-effort, process-local circuit-breaker cannot create provider credits.
It protects the existing request path on one instance; distributed quota
coordination would require a shared store. No private prompts or token values
are logged or retained.
"""
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any

from app.llms.openai_provider import OpenAILLMProvider
from app.llms.types import LLMProviderRateLimitError


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"

_COOLDOWN_SECONDS = 30.0
_cooldown_lock = Lock()
_cooldowns: dict[str, float] = {}


class GroqLLMProvider(OpenAILLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_GROQ_MODEL,
        max_output_tokens: int = 800,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        client: Any | None = None,
        reasoning_effort: str | None = None,
        text_format: dict[str, Any] | None = None,
    ) -> None:
        # Only REAL SDK clients share an opaque per-key/model cooldown.
        # Injected test clients remain independent.
        self._cooldown_key = (
            sha256((model + "\0" + api_key.strip()).encode("utf-8")).hexdigest()
            if client is None else None
        )
        self._local_deadline = 0.0
        # The OpenAI SDK retries 429 automatically if max_retries > 0.
        # A quota-exhausted Groq account must not multiply failed calls.
        # Preserve the signature for callers, but fail closed to no retries.
        del max_retries
        super().__init__(
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=0,
            client=client,
            provider_name="groq",
            provider_label="Groq",
            api_key_name="GROQ_API_KEY",
            base_url=GROQ_BASE_URL,
            send_store=False,
            reasoning_effort=reasoning_effort,
            text_format=text_format,
        )

    def _check_cooldown(self) -> None:
        now = monotonic()
        key = self._cooldown_key
        if key is None:
            deadline = self._local_deadline
        else:
            with _cooldown_lock:
                deadline = _cooldowns.get(key, 0.0)
        if now < deadline:
            raise LLMProviderRateLimitError(
                "Groq rate limit cooldown active"
            )

    def _record_cooldown(self) -> None:
        deadline = monotonic() + _COOLDOWN_SECONDS
        if self._cooldown_key is None:
            self._local_deadline = deadline
            return
        with _cooldown_lock:
            # Retain only active fingerprints; never retain credentials.
            now = monotonic()
            expired = [key for key, until in _cooldowns.items() if until <= now]
            for key in expired:
                _cooldowns.pop(key, None)
            _cooldowns[self._cooldown_key] = deadline

    def generate(self, *, instructions: str, input_text: str):
        self._check_cooldown()
        try:
            return super().generate(
                instructions=instructions, input_text=input_text,
            )
        except LLMProviderRateLimitError:
            self._record_cooldown()
            raise

    def stream(self, *, instructions: str, input_text: str):
        self._check_cooldown()
        try:
            yield from super().stream(
                instructions=instructions, input_text=input_text,
            )
        except LLMProviderRateLimitError:
            self._record_cooldown()
            raise
