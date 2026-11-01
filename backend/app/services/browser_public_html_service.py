"""Production-safe public HTML navigation without a Chromium browser.

This intentionally does not execute JavaScript, submit forms, use sessions,
follow redirects, run downloaded files, or connect to arbitrary backends.
DNS resolution is checked then pinned to the resolved *public* IPv4 address
while TLS still authenticates the original HTTPS hostname.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from lxml import html
from urllib3 import HTTPSConnectionPool, Timeout

from app.llms.types import LLMProvider
from app.schemas.browser_agent import BrowserPageEvidence, BrowserRunResponse

MAX_BYTES = 256_000


def _read_public_snapshot(url: str, host: str, ip: str) -> dict[str, Any]:
    from app.services.browser_agent_service import (
        BrowserAgentPlanError, safe_browser_url,
    )
    if safe_browser_url(url, host) is None:
        raise BrowserAgentPlanError("Unapproved public webpage")
    parsed = urlsplit(url)
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection = HTTPSConnectionPool(
        ip, port=443, assert_hostname=host, server_hostname=host,
        cert_reqs="CERT_REQUIRED", maxsize=1, block=True,
    )
    response = None
    try:
        response = connection.urlopen(
            "GET", path, retries=False, redirect=False,
            headers={
                "Host": host,
                "Accept": "text/html,text/plain",
                "Accept-Encoding": "identity",
                "User-Agent": "AqlyraReadOnlyAgent/1.0",
            },
            timeout=Timeout(connect=2.5, read=5.0),
            preload_content=False,
        )
        if response.status != 200:
            raise BrowserAgentPlanError("Public page request did not succeed")
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
        if mime not in ("text/html", "text/plain"):
            raise BrowserAgentPlanError("Only public HTML/plain text pages are allowed")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise BrowserAgentPlanError("Compressed content not allowed")
        raw = response.read(MAX_BYTES + 1, decode_content=False)
        if len(raw) > MAX_BYTES:
            raise BrowserAgentPlanError("Page exceeds public text safety budget")
        body = raw.decode("utf-8", errors="replace")
        if mime == "text/plain":
            return {"url": url, "title": host, "text": " ".join(body.split())[:6500], "links": []}
        doc = html.fromstring(body)
        title = doc.xpath("//title/text()")
        links: list[dict[str, str]] = []
        for node in doc.xpath("//a[@href]")[:100]:
            href = node.get("href") or ""
            try:
                candidate = urljoin(url, href)
            except ValueError:
                continue
            if safe_browser_url(candidate, host) is None:
                continue
            links.append({
                "href": candidate,
                "text": " ".join(node.text_content().split())[:140],
            })
        for node in doc.xpath(
            "//script|//style|//nav|//footer|//header|//aside|"
            "//svg|//form|//noscript|//template"
        ):
            node.drop_tree()
        # Prefer the substantive article/main region when it exists.
        # Keep body as a fallback for documentation sites without landmarks.
        candidates = doc.xpath("//article|//main")
        primary = max(candidates, key=lambda el: len(el.text_content()), default=None)
        region = (
            primary if primary is not None
            and len(" ".join(primary.text_content().split())) >= 40
            else doc
        )
        text = " ".join(region.text_content().split())[:6500]
        if len(text) < 20:
            raise BrowserAgentPlanError("Public page has no readable content")
        return {
            "url": url,
            "title": title[0][:180] if title else host,
            "text": text, "links": links,
        }
    except BrowserAgentPlanError:
        raise
    except Exception as exc:
        raise BrowserAgentPlanError(
            "Read-only public page fetch failed"
        ) from exc
    finally:
        if response is not None:
            response.close()
        connection.close()


async def run_read_only_html_browser(
    task: str, start_url: str, host: str, llm: LLMProvider,
) -> BrowserRunResponse:
    """Relevance-ranked same-host research with bounded recoverable dead links.

    Four *successful* pages maximum, six total HTTP attempts maximum. Broken
    secondary links never erase already collected evidence. No speculative
    cross-site navigation, writes, JS, redirects or credentials are permitted.
    """
    from app.services.browser_agent_service import (
        BrowserAgentPlanError, _validate_public_dns,
        _merge_link_frontier, _parse_choice, _rank_link_frontier,
        _canonical_public_url, safe_browser_url,
        CHOOSE_INSTRUCTIONS, SYNTH_INSTRUCTIONS,
        MAX_PAGES, MAX_LINKS, CITE_PATTERN,
    )

    pinned_ip = await _validate_public_dns(host)
    next_url = _canonical_public_url(start_url, host)
    if next_url is None:
        raise BrowserAgentPlanError("Starting public URL is not approved")
    attempted_urls: set[str] = set()
    visited_urls: set[str] = set()
    visited: list[BrowserPageEvidence] = []
    steps: list[str] = []
    frontier: list[dict[str, str]] = []
    max_attempts = MAX_PAGES + 2

    for _ in range(max_attempts):
        if len(visited) >= MAX_PAGES:
            break
        if next_url in attempted_urls:
            break
        if safe_browser_url(next_url, host) is None:
            raise BrowserAgentPlanError("Browser navigation left approved origin")
        attempted_urls.add(next_url)
        try:
            snapshot = await asyncio.to_thread(
                _read_public_snapshot, next_url, host, pinned_ip,
            )
        except BrowserAgentPlanError:
            if not visited:
                # Without any evidence, don't pretend this was successful.
                raise
            # Only retry an already-vetted alternate on the original host.
            steps.append("Skipped an unavailable approved page")
            alternatives = _rank_link_frontier([
                item for item in frontier
                if item["url"] not in attempted_urls
            ], task)
            if not alternatives:
                break
            next_url = alternatives[0]["url"]
            continue

        visited_urls.add(next_url)
        entry = BrowserPageEvidence(
            citation=f"[B{len(visited) + 1}]",
            title=snapshot["title"], url=next_url,
            excerpt=snapshot["text"][:3000],
        )
        visited.append(entry)
        steps.append(f"Read {entry.citation}: {entry.title}")
        if len(visited) >= MAX_PAGES:
            break

        frontier = _merge_link_frontier(
            frontier, snapshot["links"], next_url, host, visited_urls,
        )
        choices = _rank_link_frontier([
            option for option in frontier
            if option["url"] not in attempted_urls
        ], task)[:MAX_LINKS]
        if not choices:
            break
        output = await asyncio.to_thread(
            llm.generate,
            instructions=CHOOSE_INSTRUCTIONS,
            input_text=json.dumps({
                "task": task,
                "current_page": {
                    "url": next_url, "title": entry.title,
                    "text": snapshot["text"][:4000],
                },
                "visited_pages": [
                    {"citation": v.citation, "title": v.title} for v in visited
                ],
                "available_same_site_links": [
                    {
                        "number": index, "title": option["title"],
                        "url_path": urlsplit(option["url"]).path[:160],
                        "found_on": option["found_on"],
                    }
                    for index, option in enumerate(choices, 1)
                ],
            }, ensure_ascii=False),
        )
        index = _parse_choice(output.text, len(choices))
        if not index:
            break
        next_url = choices[index - 1]["url"]
        steps.append("Followed approved public link")

    if not visited:
        raise BrowserAgentPlanError("No approved public pages visited")
    response = await asyncio.to_thread(
        llm.generate,
        instructions=SYNTH_INSTRUCTIONS,
        input_text=json.dumps({
            "task": task,
            "visited_evidence": [v.model_dump() for v in visited],
            "navigation_notes": {
                "successful_pages": len(visited),
                "failed_link_attempts": len(attempted_urls) - len(visited),
            },
        }, ensure_ascii=False),
    )
    answer = response.text.strip()
    citations = {int(i) for i in CITE_PATTERN.findall(answer)}
    if (
        not answer or len(answer) > 12000 or not citations
        or not citations.issubset(set(range(1, len(visited) + 1)))
    ):
        raise BrowserAgentPlanError("Model lacks approved page citations")
    return BrowserRunResponse(
        task=task, answer=answer, visited=visited, steps=steps,
        finished_at=datetime.now(timezone.utc),
        model_name=response.model_name,
    )
