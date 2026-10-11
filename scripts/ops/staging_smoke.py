#!/usr/bin/env python3
"""Non-destructive checks for an Aqlyra deployment behind Caddy."""

import argparse
import ipaddress
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        return None


def validate_base_url(raw: str, allow_http_loopback: bool) -> str:
    value = raw.strip().rstrip("/")
    parsed = urlsplit(value)

    if not parsed.hostname or not parsed.netloc:
        raise ValueError("A base URL with a hostname is required")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials must not be embedded in the URL")

    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Pass an origin URL without a path, query, or fragment")

    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid TCP port") from exc

    if parsed.scheme == "https":
        return value

    is_loopback = parsed.hostname == "localhost"
    try:
        is_loopback = is_loopback or ipaddress.ip_address(
            parsed.hostname
        ).is_loopback
    except ValueError:
        pass

    if (
        parsed.scheme == "http"
        and allow_http_loopback
        and is_loopback
    ):
        return value

    raise ValueError(
        "HTTPS is required (HTTP is allowed only for explicit loopback tests)"
    )


def fetch(opener, url: str, timeout: float):
    request = Request(
        url,
        headers={
            "User-Agent": "Aqlyra-Staging-Smoke/1.0",
            "Cache-Control": "no-store",
        },
    )

    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc

    with response:
        # Bound response size: public endpoints need only tiny payloads.
        body = response.read(65537)
        return response.status, response.headers, body


def check(
    opener,
    base_url: str,
    timeout: float,
) -> list[str]:
    failures: list[str] = []

    cases = (
        ("/api/health", 200),
        ("/login", 200),
        ("/api/auth/me", 401),
        ("/api/conversations", 401),
        ("/api/v1/metrics", 404),
    )

    for path, expected in cases:
        try:
            status, headers, body = fetch(
                opener, base_url + path, timeout
            )
        except (URLError, TimeoutError, OSError) as exc:
            failures.append(f"{path}: request failed: {type(exc).__name__}")
            continue

        if status != expected:
            failures.append(
                f"{path}: expected HTTP {expected}, received HTTP {status}"
            )
            continue

        if len(body) > 65536:
            failures.append(f"{path}: response body exceeded 64 KiB")
            continue

        if path == "/api/health":
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeError):
                failures.append(f"{path}: invalid JSON response")
                continue

            if not isinstance(payload, dict) or payload.get("status") != "ready":
                failures.append(f"{path}: backend is not ready")
                continue

            if "no-store" not in headers.get("Cache-Control", "").lower():
                failures.append(f"{path}: readiness response must not be cached")
                continue

        if path == "/login":
            if "text/html" not in headers.get("Content-Type", "").lower():
                failures.append(f"{path}: login page is not HTML")
                continue

            if headers.get("X-Frame-Options", "").upper() != "DENY":
                failures.append(f"{path}: X-Frame-Options must be DENY")
                continue

            if headers.get("X-Content-Type-Options", "").lower() != "nosniff":
                failures.append(f"{path}: X-Content-Type-Options must be nosniff")
                continue

        print(f"PASS {path}: HTTP {status}")

    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", required=True,
        help="Public HTTPS origin, e.g. https://staging.example.com",
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Per-request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--allow-http-loopback",
        action="store_true",
        help="For local CI tests only; never for public staging",
    )
    args = parser.parse_args(argv)

    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be between 0 and 60 seconds")

    try:
        base_url = validate_base_url(
            args.base_url, args.allow_http_loopback
        )
    except ValueError as exc:
        parser.error(str(exc))

    failures = check(build_opener(NoRedirect()), base_url, args.timeout)
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)

    if failures:
        print(f"STAGING_SMOKE=FAIL checks_failed={len(failures)}")
        return 1

    print("STAGING_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
