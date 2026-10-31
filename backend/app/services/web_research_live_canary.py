"""Operator-opt-in, one-request real Web Research smoke (no private data).

This is intentionally not a readiness condition or a public API endpoint.
The public canary does not establish factual accuracy of the final answer.
Disable after verification to avoid API charges on future cold starts.
"""
import logging

from app.config.settings import settings
from app.services.web_research_service import (
    WebResearchEvidenceError, WebResearchUnavailable, research_web,
)
from app.services.public_office_guard import officeholder_search_query


logger = logging.getLogger(__name__)

PUBLIC_CANARY_QUESTION = "Who is Japan's current prime minister?"


def run_live_web_canary() -> bool:
    """Log sanitized end-to-end Tavily + LLM evidence status exactly once."""
    if not settings.WEB_RESEARCH_CANARY_ON_STARTUP:
        return False
    if not settings.WEB_RESEARCH_ENABLED:
        logger.warning("web_research_canary status=SKIPPED reason=disabled")
        return False
    try:
        result = research_web(
            officeholder_search_query(PUBLIC_CANARY_QUESTION),
            max_sources=4,
            mode="search",
        )
        # Web Research already validates HTTPS/public URLs, source IDs,
        # and an answer with authorized citations; do not log its text.
        if not result.sources or not result.answer.strip():
            logger.warning(
                "web_research_canary status=FAIL stage=empty_result"
            )
            return False
    except (WebResearchUnavailable, WebResearchEvidenceError) as exc:
        logger.warning(
            "web_research_canary status=FAIL error_type=%s",
            type(exc).__name__,
        )
        return False
    except Exception as exc:
        # Never log exception messages, provider payloads or credentials.
        logger.error(
            "web_research_canary status=ERROR error_type=%s",
            type(exc).__name__,
        )
        return False
    logger.info(
        "web_research_canary status=PASS provider_pipeline=verified "
        "factual_accuracy=unverified source_count=%s",
        len(result.sources),
    )
    return True
