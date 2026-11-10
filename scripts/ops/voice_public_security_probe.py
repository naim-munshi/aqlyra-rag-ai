"""Minimal production voice auth *negative* probe: no credentials, no mutations.

Runs only against the two pinned Aqlyra production origins. Deliberately
does not perform any successful login, token issuance or conversation write.
Never print response bodies or bearer tokens. Exit 2 on inaccessible
infrastructure (BLOCKED), rather than mislabeling protection as PASS.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

FRONTEND = "https://aqlyra-ai.vercel.app"
BACKEND = "https://aqlyra-api-free-launch.onrender.com"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, hdrs, newurl):
        return None


@dataclass(frozen=True)
class Check:
    label: str
    url: str
    method: str
    expected_status: int
    origin: str | None = None


CHECKS = (
    Check("frontend_voice_status_anonymous", FRONTEND + "/api/voice/status", "GET", 401),
    Check("frontend_voice_token_cross_site", FRONTEND + "/api/voice/session", "POST", 403, "https://attacker.example.invalid"),
    Check("backend_voice_status_anonymous", BACKEND + "/api/v1/voice/status", "GET", 401),
    Check("backend_voice_token_anonymous", BACKEND + "/api/v1/voice/session", "POST", 401),
)


def assess(code: int, content_type: str, body: bytes, expected: int) -> str:
    """FAIL means auth gate leaked; BLOCKED means route itself wasn't proven."""
    if 200 <= code < 300:
        return "FAIL"
    if code != expected:
        return "BLOCKED" if code in (302, 307, 308, 404, 429, 500, 502, 503, 504) else "FAIL"
    if "application/json" not in content_type.lower():
        return "BLOCKED"
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return "BLOCKED"
    if not isinstance(parsed, dict) or "participant_token" in parsed or "server_url" in parsed:
        return "FAIL"
    if not isinstance(parsed.get("detail"), str):
        return "BLOCKED"
    # A 403 JSON denial proves the negative HTTP security property even
    # when a trusted edge/middleware layer uses a different error detail.
    # It does NOT prove which layer rejected the request.
    return "PASS"


def run_one(check: Check) -> str:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Aqlyra-Voice-Security-Review/1.0",
    }
    data = None
    if check.method == "POST":
        headers["Content-Type"] = "application/json"
        data = b'{"mode":"normal"}'
    if check.origin:
        headers["Origin"] = check.origin
        headers["Sec-Fetch-Site"] = "cross-site"
    request = Request(check.url, method=check.method, headers=headers, data=data)
    try:
        with build_opener(NoRedirect()).open(request, timeout=35) as response:
            code = response.status
            mime = response.headers.get("Content-Type", "")
            body = response.read(2048)
    except HTTPError as response:
        code = response.code
        mime = response.headers.get("Content-Type", "")
        body = response.read(2048)
    except (URLError, TimeoutError, OSError):
        print(f"voice_security_probe_http: {check.label}=UNREACHABLE")
        return "BLOCKED"
    # Safe diagnostics only: never print URLs, headers, response bodies or tokens.
    is_json = "application/json" in mime.lower()
    print(
        f"voice_security_probe_http: {check.label}=HTTP_{code}"
        f" expected=HTTP_{check.expected_status} json={is_json}"
    )
    return assess(code, mime, body, check.expected_status)


def main() -> int:
    states: list[str] = []
    for check in CHECKS:
        state = run_one(check)
        states.append(state)
        print(f"voice_security_negative_probe: {check.label}={state}")
    final = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"
    print(f"voice_security_negative_probe_final={final}")
    # Never report protected/inaccessible production as a verified PASS.
    return 1 if final == "FAIL" else 2 if final == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
