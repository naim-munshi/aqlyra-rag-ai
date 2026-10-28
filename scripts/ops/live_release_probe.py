#!/usr/bin/env python3
"""Read-only production readiness diagnostic for the exact Aqlyra Render origin.

Makes no writes, requests no credentials, follows no redirects, does not
create test users, and never outputs response body. Does not replace real
authenticated provider E2E, backup/restore, or an agent audio round trip.
"""
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ORIGIN = "https://aqlyra-api-free-launch.onrender.com"
MAX_BODY = 32768


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        return None


def probe(path: str) -> tuple[int, object | None]:
    request = Request(
        ORIGIN + path,
        headers={
            "User-Agent": "Aqlyra-ReadOnly-CIGate/1.0",
            "Cache-Control": "no-store",
        },
        method="GET",
    )
    opener = build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=35)
    except HTTPError as exc:
        response = exc
    with response:
        status = response.status
        data = response.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise ValueError("Oversized response")
        if not data:
            return status, None
        try:
            return status, json.loads(data)
        except (UnicodeError, ValueError):
            return status, None


def main() -> int:
    checks = [
        ("liveness", "/api/v1/health", 200),
        ("database_storage_redis", "/api/v1/readiness", 200),
        ("study_abroad_workflow", "/api/v1/study-abroad/workflows", 200),
        ("anonymous_study_cases_denied", "/api/v1/study-abroad/cases", 401),
    ]
    failures = []
    for name, path, expected in checks:
        try:
            status, payload = probe(path)
            valid = status == expected
            if valid and name == "liveness":
                valid = isinstance(payload, dict) and payload.get("status") == "healthy"
            if valid and name == "database_storage_redis":
                valid = (
                    isinstance(payload, dict)
                    and payload.get("status") == "ready"
                    and isinstance(payload.get("checks"), dict)
                    and all(
                        payload["checks"].get(k) == "ready"
                        for k in ("database", "storage", "redis")
                    )
                )
            if valid and name == "study_abroad_workflow":
                valid = isinstance(payload, list) and any(
                    isinstance(workflow, dict)
                    and workflow.get("id") == "student"
                    and workflow.get("enabled") is True
                    for workflow in payload
                )
            if valid:
                print(f"PASS {name}: HTTP {status}", flush=True)
            else:
                reason = ""
                # Whitelist safe generic backend readiness messages only.
                # Never emit arbitrary server response bodies or exception data.
                if name == "database_storage_redis" and status == 503:
                    if isinstance(payload, dict) and payload.get("detail") == (
                        "Service dependencies are unavailable"
                    ):
                        reason = " (Redis rate-limit dependency unavailable)"
                    elif isinstance(payload, dict) and payload.get("detail") == (
                        "Service is not ready"
                    ):
                        reason = " (database/schema/upload readiness blocked)"
                print(
                    f"BLOCKED {name}: HTTP {status}, expected {expected} plus contract{reason}",
                    flush=True,
                )
                failures.append(name)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            print(
                f"BLOCKED {name}: {type(exc).__name__} (no body disclosed)",
                flush=True,
            )
            failures.append(name)
    if failures:
        print(f"LIVE_RELEASE_GATE=BLOCKED count={len(failures)}", flush=True)
        return 1
    print("LIVE_RELEASE_GATE=PASS (read-only, not real provider E2E)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
