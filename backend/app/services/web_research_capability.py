"""Non-secret release diagnostics for Aqlyra's public Web Research provider.

"configured" never implies that live Tavily requests, network egress, credits,
freshness, source extraction or LLM citations have passed production acceptance.
"""
from app.config.settings import settings
from app.services.searxng_provider import configured_searxng_url


def public_web_research_status() -> str:
    enabled = settings.WEB_RESEARCH_ENABLED
    # Preserve old Tavily-only diagnostics for existing installations;
    # report keyless search independently when a trusted URL is configured.
    searxng = configured_searxng_url()
    if enabled and searxng and settings.WEB_SEARCH_PROVIDER in ("auto", "searxng"):
        return "searxng_configured_unverified"
    if enabled and settings.WEB_SEARCH_PROVIDER == "searxng" and not searxng:
        return "missing_searxng_url"
    if enabled and settings.WEB_SEARCH_PROVIDER == "tavily" and not settings.TAVILY_API_KEY.strip():
        return "missing_tavily_api_key"
    key_present = bool(settings.TAVILY_API_KEY.strip())
    if not enabled and not key_present:
        return "disabled_and_missing_key"
    if not enabled:
        return "disabled_key_present"
    if not key_present:
        return "missing_tavily_api_key"
    return "configured_unverified"
