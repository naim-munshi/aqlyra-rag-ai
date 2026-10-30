"""Non-secret release diagnostics for Aqlyra's public Web Research provider.

"configured" never implies that live Tavily requests, network egress, credits,
freshness, source extraction or LLM citations have passed production acceptance.
"""
from app.config.settings import settings


def public_web_research_status() -> str:
    if not settings.WEB_RESEARCH_ENABLED:
        return "disabled"
    if not settings.TAVILY_API_KEY.strip():
        return "missing_tavily_api_key"
    return "configured_unverified"
