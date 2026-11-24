"""Public-only one-shot keyless SearXNG → Groq production acceptance.

Never read private chat, user memory, documents or credentials. The
operator-only flag is OFF by default and should be turned off after one test.
"""
import logging

from app.config.settings import settings
from app.services.web_research_service import (
    WebResearchEvidenceError,
    WebResearchUnavailable,
    _research_web_searxng,
)
from app.services.searxng_provider import configured_searxng_url

logger = logging.getLogger(__name__)

_PUBLIC_QUESTION = "What is Bangladesh?"


def run_keyless_web_canary() -> bool:
    if not settings.WEB_KEYLESS_CANARY_ON_STARTUP:
        return False
    if not settings.WEB_RESEARCH_ENABLED or not configured_searxng_url():
        logger.warning("keyless_web_canary status=SKIPPED reason=not_configured")
        return False
    try:
        result = _research_web_searxng(
            _PUBLIC_QUESTION, max_sources=4, mode="search",
        )
        if not result.sources or not result.answer:
            logger.warning("keyless_web_canary status=FAIL stage=empty_evidence")
            return False
    except (WebResearchUnavailable, WebResearchEvidenceError) as exc:
        logger.warning(
            "keyless_web_canary status=FAIL error_type=%s",
            type(exc).__name__,
        )
        return False
    except Exception as exc:
        logger.warning(
            "keyless_web_canary status=ERROR error_type=%s",
            type(exc).__name__,
        )
        return False
    logger.info(
        "keyless_web_canary status=PASS source_count=%s "
        "answer_citations=validated real_time_accuracy=unverified",
        len(result.sources),
    )
    return True
