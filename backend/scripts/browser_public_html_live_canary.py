"""Bounded, anonymous *real-network* HTML Browser Agent acceptance canary.

This does NOT test private users, Playwright automation, model-generated
answers or the Render production environment. It tests that the existing
pinned-DNS/TLS public HTML reader can fetch one public document from CI.
No cookies, tokens, credentials, redirects, writes or logged response text.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from app.services.browser_agent_service import (
    BrowserAgentPlanError, _validate_public_dns, safe_browser_url,
)
from app.services.browser_public_html_service import _read_public_snapshot

# Fixed test destinations; never accept an arbitrary domain from CI input.
_CANARY_URLS = (
    "https://example.com/",
    "https://www.example.com/",
)


async def verify_one(url: str) -> tuple[str, str]:
    """Return sanitized status only: (PASS/BLOCKED, reason-code)."""
    host = urlsplit(url).hostname or ""
    if safe_browser_url(url, host) is None:
        return "BLOCKED", "URL_POLICY"
    try:
        ip = await _validate_public_dns(host)
        page = await asyncio.wait_for(
            asyncio.to_thread(_read_public_snapshot, url, host, ip),
            timeout=12,
        )
        if (
            page.get("url") != url
            or not isinstance(page.get("text"), str)
            or len(page["text"].strip()) < 25
        ):
            return "BLOCKED", "EMPTY_EVIDENCE"
        if any(
            safe_browser_url(item.get("href"), host) is None
            for item in page.get("links", [])
        ):
            return "BLOCKED", "UNSAFE_LINKS"
    except (BrowserAgentPlanError, TimeoutError, OSError):
        return "BLOCKED", "NETWORK_OR_PAGE"
    return "PASS", "PINNED_TLS_HTML"


async def main_async() -> int:
    # Avoid unrestricted host discovery: a single successful example
    # page is sufficient to prove a real HTTPS reader request.
    for index, url in enumerate(_CANARY_URLS, 1):
        status, reason = await verify_one(url)
        print(f"browser_public_html_live_canary: candidate={index} status={status} reason={reason}")
        if status == "PASS":
            print("browser_public_html_live_canary_final=PASS")
            return 0
    print("browser_public_html_live_canary_final=BLOCKED")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
