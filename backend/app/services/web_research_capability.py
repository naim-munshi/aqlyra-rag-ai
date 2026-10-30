"""Non-secret release diagnostics for Aqlyra's public Web Research provider.

"configured" never implies that live Tavily requests, network egress, credits,
freshness, source extraction or LLM citations have passed production acceptance.
"""
from app.config.settings import settings


def public_web_research_status() -> str:
    enabled = settings.WEB_RESEARCH_ENABLED
    key_present = bool(settings.TAVILY_API_KEY.strip())
    if not enabled and not key_present:
        return "disabled_and_missing_key"
    if not enabled:
        return "disabled_key_present"
    if not key_present:
        return "missing_tavily_api_key"
    return "configured_unverified"
