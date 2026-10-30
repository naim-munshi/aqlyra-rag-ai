"""SearXNG JSON search adapter: public query only, bounded and keyless.

A SearXNG instance is configured server-side (never from user query).
Requires JSON format explicitly enabled on the self-hosted instance.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from typing import Any

import httpx

from app.config.settings import settings

MAX_JSON_BYTES = 800_000


def configured_searxng_url() -> str | None:
    raw = settings.SEARXNG_BASE_URL.strip().rstrip("/")
    if not raw or len(raw) > 240:
        return None
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not host or "." not in host or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment
            or any(x.isspace() for x in raw)
        ):
            return None
        if host in {"localhost", "metadata.google.internal"} or host.endswith(
            (".local", ".internal", ".localhost", ".test", ".invalid")
        ):
            return None
        import ipaddress
        try:
            ipaddress.ip_address(host)
            return None
        except ValueError:
            pass
        return raw
    except ValueError:
        return None


def search_searxng(
    question: str, *, client: httpx.Client,
    limit: int, time_range: str | None = None,
) -> list[dict[str, Any]]:
    from app.services.web_research_service import (
        WebResearchUnavailable, safe_public_url,
    )

    base = configured_searxng_url()
    if not base:
        raise WebResearchUnavailable("SearXNG is not configured with a valid HTTPS URL")
    if not 1 <= limit <= 10 or not 3 <= len(question) <= 600:
        raise ValueError("Invalid bounded SearXNG search")
    params: dict[str, str | int] = {
        "q": question, "format": "json", "safesearch": 1,
        "language": "auto", "pageno": 1,
    }
    if time_range in {"day", "month", "year"}:
        params["time_range"] = time_range
    try:
        response = client.get(
            base + "/search", params=params,
            headers={"Accept": "application/json"},
            timeout=8.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        if len(response.content) > MAX_JSON_BYTES:
            raise WebResearchUnavailable("SearXNG response exceeded safe limit")
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WebResearchUnavailable("SearXNG service unavailable") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise WebResearchUnavailable("SearXNG did not return valid JSON search results")
    safe: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload["results"][: min(30, limit * 3)]:
        if not isinstance(item, dict):
            continue
        url = safe_public_url(item.get("url"))
        if not url or url in seen:
            continue
        title = item.get("title") or url
        snippet = item.get("content")
        seen.add(url)
        safe.append({
            "url": url,
            "title": title[:180] if isinstance(title, str) else url,
            "published_date": (
                item["publishedDate"][:32]
                if isinstance(item.get("publishedDate"), str)
                else None
            ),
            "content": snippet[:1200] if isinstance(snippet, str) else "",
        })
        if len(safe) >= limit:
            break
    return safe
