"""Token-protected minimal SearXNG JSON gateway for a public Render Web Service.

Public GET /healthz is a readiness check only. Search requires a strong
constant-time compared secret. There is NO open search API, browsing proxy,
URL fetch route, logging of queries, or response redirect.
"""
from __future__ import annotations

import hmac
import http.client
import html
import re
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

MAX_BYTES = 800_000
ALLOWED_KEYS = {"q", "format", "safesearch", "language", "pageno", "time_range"}
TIME_RANGES = {"day", "month", "year"}


def validated_search_path(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        if parsed.path != "/search" or parsed.scheme or parsed.netloc or parsed.fragment:
            return None
        params = parse_qs(
            parsed.query, strict_parsing=True,
            max_num_fields=8, keep_blank_values=False,
        )
        if not params or not set(params).issubset(ALLOWED_KEYS):
            return None
        if any(len(v) != 1 for v in params.values()):
            return None
        query = params.get("q", [""])[0]
        if not 3 <= len(query) <= 600 or any(ord(c) < 32 for c in query):
            return None
        if params.get("format") != ["json"]:
            return None
        if params.get("pageno", ["1"]) != ["1"]:
            return None
        if params.get("safesearch", ["1"]) != ["1"]:
            return None
        if params.get("time_range", ["day"])[0] not in TIME_RANGES:
            return None
        return "/search?" + urlencode({
            "q": query, "format": "json", "pageno": "1", "safesearch": "1",
            "language": "auto",
            **(
                {"time_range": params["time_range"][0]}
                if "time_range" in params else {}
            ),
        })
    except (ValueError, UnicodeError):
        return None


def wikipedia_public_search(query: str, *, limit: int = 5) -> list[dict[str, str]]:
    """Fixed Wikimedia API fallback; never a general outbound URL proxy.

    Only actual MediaWiki search hits with page IDs enter the result set.
    HTTPS and certificate validation are enforced by HTTPSConnection.
    """
    if not 3 <= len(query) <= 600 or not 1 <= limit <= 5:
        return []
    connection = None
    try:
        connection = http.client.HTTPSConnection(
            "en.wikipedia.org", 443, timeout=3.0,
        )
        path = "/w/api.php?" + urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": str(limit), "format": "json", "formatversion": "2",
        })
        connection.request("GET", path, headers={
            "User-Agent": "AqlyraPublicSearch/1.0 (noncommercial; source-linked)",
            "Accept": "application/json",
        })
        response = connection.getresponse()
        if response.status != 200:
            return []
        if not response.getheader("Content-Type", "").lower().startswith("application/json"):
            return []
        raw = response.read(180001)
        if len(raw) > 180000:
            return []
        payload = json.loads(raw)
        hits = payload.get("query", {}).get("search", [])
        if not isinstance(hits, list):
            return []
        results: list[dict[str, str]] = []
        for item in hits[:limit]:
            if not isinstance(item, dict):
                continue
            page_id = item.get("pageid")
            title = item.get("title")
            if type(page_id) is not int or page_id <= 0 or not isinstance(title, str):
                continue
            snippet = item.get("snippet", "")
            plain = html.unescape(re.sub(r"<[^>]*>", " ", snippet)) if isinstance(snippet, str) else ""
            results.append({
                "url": f"https://en.wikipedia.org/?curid={page_id}",
                "title": title[:180],
                "content": " ".join(plain.split())[:1200],
                "engine": "wikipedia-api",
            })
        return results
    except (OSError, ValueError, TypeError, KeyError):
        return []
    finally:
        if connection is not None:
            connection.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Never log search queries or token-bearing request headers.
        pass

    def send_json_error(self, status: int, reason: str) -> None:
        body = json.dumps({"error": reason}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            try:
                with socket.create_connection(("127.0.0.1", 8080), timeout=1.0):
                    self.send_json_error(200, "ready")
            except OSError:
                self.send_json_error(503, "starting")
            return
        secret = os.environ.get("SEARXNG_SERVICE_TOKEN", "")
        supplied = self.headers.get("X-Aqlyra-Search-Token", "")
        if len(secret) < 32:
            self.send_json_error(503, "gateway-not-configured")
            return
        if not hmac.compare_digest(
            secret.encode(), supplied.encode()[:256],
        ):
            self.send_json_error(401, "unauthorized")
            return
        path = validated_search_path(self.path)
        if path is None:
            self.send_json_error(400, "bad-search-request")
            return
        connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=4)
        try:
            connection.request(
                "GET", path,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Aqlyra/1.0",
                    "X-Forwarded-For": "127.0.0.1",
                    "X-Real-IP": "127.0.0.1",
                },
            )
            response = connection.getresponse()
            content = response.read(MAX_BYTES + 1)
            mime = response.getheader("Content-Type", "").split(";", 1)[0].lower()
            if response.status != 200 or mime != "application/json":
                self.send_json_error(503, "upstream-search-unavailable")
                return
            if len(content) > MAX_BYTES:
                self.send_json_error(502, "upstream-too-large")
                return
            try:
                payload = json.loads(content)
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    self.send_json_error(503, "invalid-search-response")
                    return
                if not payload["results"]:
                    query = parse_qs(urlsplit(path).query).get("q", [""])[0]
                    fallback = wikipedia_public_search(query)
                    if fallback:
                        payload["results"] = fallback
                        content = json.dumps(payload, ensure_ascii=False).encode()
            except (ValueError, UnicodeError, TypeError):
                self.send_json_error(503, "invalid-search-response")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (OSError, ValueError, TimeoutError):
            self.send_json_error(503, "upstream-search-unavailable")
        finally:
            connection.close()


def startup_search_probe() -> None:
    """One fixed public query per boot; never collect users' search content."""
    # Granian binds its socket before worker-1 has finished loading engines.
    # A 6-second probe races the startup and yields a false DEGRADED.
    time.sleep(22)
    connection = http.client.HTTPConnection(
        "127.0.0.1", int(os.environ.get("PORT", "10000")), timeout=14
    )
    try:
        # Probe the token-authenticated public gateway, including the
        # fixed-source fallback, not just SearXNG's sometimes empty backend.
        connection.request(
            "GET", "/search?q=Bangladesh&format=json",
            headers={
                "Accept": "application/json",
                "X-Aqlyra-Search-Token": os.environ["SEARXNG_SERVICE_TOKEN"],
            },
        )
        reply = connection.getresponse()
        raw = reply.read(MAX_BYTES + 1)
        if reply.status != 200 or len(raw) > MAX_BYTES:
            print("SEARXNG_SEARCH_PROBE=DEGRADED", flush=True)
            return
        data = json.loads(raw)
        results = data.get("results") if isinstance(data, dict) else None
        count = len(results) if isinstance(results, list) else 0
        print(
            f"SEARXNG_SEARCH_PROBE={'PASS' if count else 'DEGRADED'} "
            f"result_count={min(count, 999)}",
            flush=True,
        )
    except (OSError, ValueError, TimeoutError):
        print("SEARXNG_SEARCH_PROBE=DEGRADED", flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    threading.Thread(target=startup_search_probe, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise SystemExit("invalid PORT")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
