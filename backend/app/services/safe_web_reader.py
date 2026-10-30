"""Bounded HTTPS page extraction with DNS-pinned TLS and SSRF protections.

Only used on public search result URLs, never internal cloud endpoints. Remote
HTML is evidence (not instructions); scripts are discarded and never executed.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from lxml import html
from urllib3 import HTTPSConnectionPool, Timeout

MAX_PAGE_BYTES = 262_144
MAX_PAGE_CHARS = 3_000


def resolve_public_ipv4(hostname: str) -> str | None:
    """Reject a host if ANY IPv4 DNS answer is private/reserved or unsafe."""
    try:
        entries = socket.getaddrinfo(
            hostname, 443, family=socket.AF_INET, type=socket.SOCK_STREAM,
        )
    except (OSError, ValueError):
        return None
    addresses = {entry[4][0] for entry in entries}
    if not addresses or len(addresses) > 16:
        return None
    if any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        return None
    return sorted(addresses)[0]


def fetch_public_page(url: str) -> str | None:
    """Pin checked public DNS IP for HTTPS while verifying TLS for hostname.

    No redirects, proxies, cookie forwarding, JS, credential-bearing headers,
    non-HTTPS requests, or unbounded response bodies.
    """
    from app.services.web_research_service import safe_public_url

    if not safe_public_url(url):
        return None
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if not hostname:
        return None
    ip = resolve_public_ipv4(hostname)
    if not ip:
        return None
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection = HTTPSConnectionPool(
        ip, port=443,
        assert_hostname=hostname,
        server_hostname=hostname,
        cert_reqs="CERT_REQUIRED",
        maxsize=1,
        block=True,
    )
    response = None
    try:
        response = connection.urlopen(
            "GET", path, retries=False, redirect=False,
            headers={
                "Host": hostname,
                "User-Agent": "AqlyraPublicResearch/1.0 (+source-citations)",
                "Accept": "text/html,text/plain",
                "Accept-Encoding": "identity",
            },
            timeout=Timeout(connect=2.5, read=4.0),
            preload_content=False,
        )
        if response.status != 200:
            return None
        mime = response.headers.get("Content-Type", "").lower().split(";", 1)[0]
        if mime not in ("text/html", "text/plain"):
            return None
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            return None
        raw = response.read(MAX_PAGE_BYTES + 1, decode_content=False)
        if len(raw) > MAX_PAGE_BYTES:
            return None
        decoded = raw.decode("utf-8", errors="replace")
        if mime == "text/html":
            doc = html.fromstring(decoded)
            for node in doc.xpath("//script|//style|//nav|//footer|//svg|//form|//noscript"):
                node.drop_tree()
            decoded = doc.text_content()
        text = " ".join(decoded.split())
        return text[:MAX_PAGE_CHARS] if len(text) >= 80 else None
    except Exception:
        # Fail closed on DNS, TLS, timeouts, malformed HTML and network errors.
        return None
    finally:
        if response is not None:
            response.close()
        connection.close()
