"""Operator-only, sanitized public HTML Browser Agent acceptance on boot."""
import asyncio
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)

_PUBLIC_TEST_URL = "https://example.com/"


def run_browser_html_canary() -> bool:
    if not settings.BROWSER_AGENT_HTML_CANARY_ON_STARTUP:
        return False
    if not (
        settings.BROWSER_AGENT_HTML_ONLY_PRODUCTION_ENABLED
        and settings.BROWSER_APPROVAL_REDIS_ENABLED
        and settings.BROWSER_AGENT_ENABLED
        and "example.com" in {
            host.strip().lower() for host in settings.BROWSER_AGENT_ALLOWED_HOSTS.split(",")
        }
    ):
        logger.warning("browser_html_canary status=SKIPPED reason=feature_gates")
        return False
    try:
        import redis
        from app.services.browser_agent_service import _validate_public_dns
        from app.services.browser_public_html_service import _read_public_snapshot
        cache = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=2,
            socket_timeout=2, decode_responses=True,
        )
        if not cache.ping():
            raise RuntimeError("Redis unavailable")
        pinned_ip = asyncio.run(_validate_public_dns("example.com"))
        page = _read_public_snapshot(_PUBLIC_TEST_URL, "example.com", pinned_ip)
        if not page.get("text"):
            raise RuntimeError("Public page empty")
        logger.info(
            "browser_html_canary status=PASS public_pages=1 "
            "redis_approval_store=ready javascript=disabled"
        )
        return True
    except Exception as exc:
        logger.warning(
            "browser_html_canary status=FAIL error_type=%s",
            type(exc).__name__,
        )
        return False
