"""Opt-in single-call model selection for substantive normal-chat requests.

No separate classifier API request, hidden tools, conversation history,
private memory or documents are sent to a new provider by this module.
Disabled by default. Keep the existing configured model for all other turns.
"""
import re

from app.config.settings import settings
from app.llms import (
    LLMProvider,
    create_configured_llm_provider,
    create_llm_provider,
)


_COMPLEX_REQUEST = re.compile(
    r"\b(?:analy[sz]e|comparison|compare|evaluate|"
    r"trade[ -]?offs?|architecture|root cause|debug|"
    r"troubleshoot|roadmap|strategic plan|"
    r"step[ -]by[ -]step|deep review|deep research)\b"
    r"|তুলনা|বিশ্লেষণ|পরিকল্পনা|আর্কিটেকচার|সমস্যার কারণ|রোডম্যাপ"
    r"|比較|分析|設計|原因調査|改善計画|アーキテクチャ",
    re.IGNORECASE,
)

# A production quality-tier allowlist avoids arbitrary model strings from
# silently creating unsupported provider requests or paid provider changes.
_ALLOWED_GROQ_QUALITY_MODELS = frozenset({
    "openai/gpt-oss-120b",
})


def is_complex_request(message: str) -> bool:
    """Conservative explicit-intent classifier, no user-data disclosure."""
    if not isinstance(message, str) or len(message) > 12_000:
        return False
    return bool(_COMPLEX_REQUEST.search(message))


def select_provider_for_normal_chat(
    *,
    message: str,
    provider: LLMProvider | None = None,
) -> LLMProvider:
    """Return exactly one configured provider; never call a second LLM.

    An injected test provider is authoritative. All other traffic retains
    the original configured provider unless the feature is explicitly
    enabled, the selected model is allowlisted, and the user clearly asks
    a complex task. Upstream rate limits still apply.
    """
    if provider is not None:
        return provider

    quality_model = settings.LLM_QUALITY_MODEL.strip()
    if not (
        settings.LLM_QUALITY_ROUTING_ENABLED
        and settings.LLM_PROVIDER == "groq"
        and settings.GROQ_API_KEY.strip()
        and quality_model in _ALLOWED_GROQ_QUALITY_MODELS
        and quality_model != settings.LLM_MODEL
        and is_complex_request(message)
    ):
        return create_configured_llm_provider()

    return create_llm_provider(
        provider_name="groq",
        model_name=quality_model,
        api_key=settings.GROQ_API_KEY,
        max_output_tokens=settings.LLM_QUALITY_MAX_OUTPUT_TOKENS,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        # Repeating rate-limited requests can multiply daily free-tier use.
        max_retries=0,
        reasoning_effort="medium",
    )
