#!/usr/bin/env python3
"""Two-account PRIVATE ARTIFACT API acceptance on an isolated disposable stage.

This intentionally does not claim frontend UI, real LLM generation, restart
persistence or backups. No users are registered/deleted; only synthetic files
created during this invocation are deleted. Passwords/tokens are never logged.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from staging_smoke import validate_base_url

_FORMATS = ("md", "pdf", "docx", "xlsx", "pptx")
_PROD_HOSTS = {
    "aqlyra-ai.vercel.app",
    "aqlyra-navy.vercel.app",
    "aqlyra-aqlyra.vercel.app",
    "aqlyra-api-free-launch.onrender.com",
    "aqlyra-semantic-worker.onrender.com",
}
_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_MAX_BYTES = 26 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        return None


class SmokeFailure(Exception):
    """Only sanitized failure details may be displayed."""


def require_disposable_target(raw: str, *, allow_loopback: bool) -> str:
    base = validate_base_url(raw, allow_loopback)
    host = (urlsplit(base).hostname or "").lower()
    if host in _PROD_HOSTS:
        raise ValueError("Refusing known production hostname")
    is_loopback = host in ("localhost", "127.0.0.1", "::1")
    if not is_loopback and not (
        host.startswith("staging.") or host.startswith("stage.")
        or "-staging-" in host or "-stage-" in host
        or host.startswith("staging-") or host.startswith("stage-")
    ):
        raise ValueError("A clearly named staging hostname is required")
    return base


class Client:
    def __init__(self, base_url: str, timeout: float = 15):
        self.base_url = base_url
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def request(self, method: str, path: str, *, token: str = "", data: dict | None = None):
        if not path.startswith("/api/v1/") or "?" in path or "#" in path:
            raise SmokeFailure("Unsafe API path")
        headers = {"Accept": "application/json", "Cache-Control": "no-store"}
        if token:
            if "\n" in token or "\r" in token:
                raise SmokeFailure("Invalid authentication token")
            headers["Authorization"] = "Bearer " + token
        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        request = Request(
            self.base_url + path, data=body, headers=headers, method=method,
        )
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except HTTPError as exc:
            response = exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SmokeFailure("API transport unavailable: " + type(exc).__name__) from exc
        with response:
            blob = response.read(_MAX_BYTES + 1)
            if len(blob) > _MAX_BYTES:
                raise SmokeFailure("API response exceeded safe size")
            return response.status, response.headers, blob


def json_response(blob: bytes) -> dict:
    try:
        payload = json.loads(blob)
    except (TypeError, UnicodeError, ValueError) as exc:
        raise SmokeFailure("Unexpected JSON response") from exc
    if not isinstance(payload, dict):
        raise SmokeFailure("Expected JSON object")
    return payload


def expect(status: int, expected: int, step: str) -> None:
    if status != expected:
        # Never print provider responses, user messages, bearer tokens, URLs or HTML.
        raise SmokeFailure(f"{step}: expected HTTP {expected}, got {status}")


def login(client: Client, email: str, password: str) -> str:
    status, _, blob = client.request(
        "POST", "/api/v1/auth/login",
        data={"email": email, "password": password},
    )
    expect(status, 200, "login")
    token = json_response(blob).get("access_token")
    if not isinstance(token, str) or len(token) < 16:
        raise SmokeFailure("Login token unavailable")
    return token


def file_signature_ok(kind: str, blob: bytes) -> bool:
    if kind == "md":
        return blob.startswith(b"# Staging artifact")
    if kind == "pdf":
        return blob.startswith(b"%PDF-")
    return blob.startswith(b"PK\x03\x04")


def run(client: Client, account_a: tuple[str, str], account_b: tuple[str, str]) -> None:
    if account_a[0].lower() == account_b[0].lower():
        raise SmokeFailure("Two independent staging accounts required")
    alpha = login(client, *account_a)
    beta = login(client, *account_b)
    path = "/api/v1/artifacts"
    created: list[str] = []
    try:
        status, _, body = client.request("GET", path, token=beta)
        expect(status, 200, "secondary account inventory")
        prior = json_response(body).get("items")
        if not isinstance(prior, list):
            raise SmokeFailure("Secondary inventory invalid")

        for fmt in _FORMATS:
            status, _, raw = client.request("POST", path + "/render", token=alpha, data={
                "title": "Staging artifact - synthetic",
                "format": fmt,
                "content": "# Staging artifact\nSynthetic staging-only content.",
            })
            expect(status, 201, "create " + fmt)
            item = json_response(raw)
            artifact_id = item.get("id")
            if not isinstance(artifact_id, str) or not _ID.fullmatch(artifact_id):
                raise SmokeFailure("Invalid created artifact ID")
            created.append(artifact_id)
            if item.get("format") != fmt:
                raise SmokeFailure("Created format mismatch")
            for operation in ("GET", "DELETE"):
                suffix = "/download" if operation == "GET" else ""
                status, _, _ = client.request(operation, path + "/" + artifact_id + suffix, token=beta)
                expect(status, 404, "cross-account " + operation)

            status, headers, downloaded = client.request(
                "GET", path + "/" + artifact_id + "/download", token=alpha,
            )
            expect(status, 200, "owner download " + fmt)
            if not file_signature_ok(fmt, downloaded):
                raise SmokeFailure("Downloaded file magic mismatch: " + fmt)
            if int(item.get("size", -1)) != len(downloaded):
                raise SmokeFailure("Downloaded file size mismatch")
            if "attachment" not in headers.get("Content-Disposition", "").lower():
                raise SmokeFailure("Download must be an attachment")
            if "no-store" not in headers.get("Cache-Control", "").lower():
                raise SmokeFailure("Private response must not be cached")
            if headers.get("X-Content-Type-Options", "").lower() != "nosniff":
                raise SmokeFailure("Download requires nosniff")
            print("PASS synthetic-" + fmt + " create, private download, owner isolation")

        status, _, raw = client.request("GET", path, token=beta)
        expect(status, 200, "secondary account inventory")
        foreign = json_response(raw).get("items")
        if not isinstance(foreign, list) or any(
            isinstance(x, dict) and x.get("id") in created for x in foreign
        ):
            raise SmokeFailure("Cross-account inventory exposure")
        print("PASS two-account inventory isolation")
    finally:
        # Never enumerate/delete anything other than exact IDs created here.
        cleanup_failed = False
        for artifact_id in created:
            try:
                status, _, _ = client.request("DELETE", path + "/" + artifact_id, token=alpha)
                if status != 204:
                    cleanup_failed = True
                status, _, _ = client.request("GET", path + "/" + artifact_id, token=alpha)
                if status != 404:
                    cleanup_failed = True
            except SmokeFailure:
                cleanup_failed = True
        if cleanup_failed:
            raise SmokeFailure("Synthetic artifact cleanup FAILED; inspect staging safely")
        if created:
            print("PASS exact-ID cleanup; no user records modified")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="A disposable *backend API* staging origin")
    parser.add_argument("--ack-disposable-staging", action="store_true")
    parser.add_argument("--allow-http-loopback", action="store_true")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args(argv)
    if not args.ack_disposable_staging:
        parser.error("Explicit --ack-disposable-staging is required")
    if not 0 < args.timeout <= 30:
        parser.error("Timeout must be within 0-30 seconds")
    try:
        origin = require_disposable_target(args.base_url, allow_loopback=args.allow_http_loopback)
    except ValueError as exc:
        parser.error(str(exc))
    names = ("AQLYRA_E2E_A_EMAIL", "AQLYRA_E2E_A_PASSWORD",
             "AQLYRA_E2E_B_EMAIL", "AQLYRA_E2E_B_PASSWORD")
    secrets = tuple(os.environ.get(name, "") for name in names)
    if any(not x for x in secrets):
        parser.error("Four independent staging test-account environment values are required")
    try:
        run(Client(origin, args.timeout), (secrets[0], secrets[1]), (secrets[2], secrets[3]))
    except SmokeFailure as exc:
        print("ARTIFACT_STAGING_E2E=FAIL " + str(exc), file=sys.stderr)
        return 1
    print("ARTIFACT_STAGING_E2E=PASS scope=api-only voice=not-tested ui=not-tested backups=not-tested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
