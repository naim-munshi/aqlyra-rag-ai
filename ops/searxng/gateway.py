"""Token-protected minimal SearXNG JSON gateway for a public Render Web Service.

Public GET /healthz is a readiness check only. Search requires a strong
constant-time compared secret. There is NO open search API, browsing proxy,
URL fetch route, logging of queries, or response redirect.
"""
from __future__ import annotations

import hmac
import http.client
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
        connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=9)
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
    connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=12)
    try:
        connection.request(
            "GET", "/search?q=Bangladesh&format=json",
            headers={
                "Accept": "application/json",
                "X-Forwarded-For": "127.0.0.1",
                "X-Real-IP": "127.0.0.1",
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
