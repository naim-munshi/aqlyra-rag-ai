#!/usr/bin/env python3
"""Authenticated, disposable two-account E2E through the real frontend BFF and backend."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
from http.cookies import SimpleCookie
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ACCESS_COOKIE = "aqlyra_access_token"
REFRESH_COOKIE = "aqlyra_refresh_token"
MAX_RESPONSE_BYTES = 256 * 1024


class E2EError(RuntimeError):
    pass


def _validate_loopback_origin(value: str) -> str:
    base = value.strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("A valid HTTP(S) base URL is required")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials must not be embedded in the base URL")
    try:
        is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        is_loopback = parsed.hostname.lower() == "localhost"
    if not is_loopback:
        raise ValueError("This credentialed E2E runner is restricted to loopback")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Pass an origin URL without a path, query, or fragment")
    return base


class BrowserSession:
    """Tiny cookie-aware client that models a browser on CI loopback.

    Secure cookies are retained and replayed manually because the test origin is
    HTTP localhost. They are never sent to a non-loopback host.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.cookies: dict[str, str] = {}

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        expected_status: int,
    ) -> tuple[int, object]:
        headers = {
            "Accept": "application/json",
            "Cache-Control": "no-store",
            "Origin": self.base_url,
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Aqlyra-Fullstack-E2E/1.0",
        }
        if self.cookies:
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in self.cookies.items()
            )
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")

        request = Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError) as error:
            raise E2EError(
                f"{method} {path}: transport failed ({type(error).__name__})"
            ) from error

        with response:
            self._capture_cookies(response.headers.get_all("Set-Cookie", []))
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status

        if len(raw) > MAX_RESPONSE_BYTES:
            raise E2EError(f"{method} {path}: response exceeded the size limit")
        try:
            data = json.loads(raw) if raw else None
        except (ValueError, UnicodeError) as error:
            raise E2EError(f"{method} {path}: expected JSON response") from error

        if status != expected_status:
            detail = data.get("detail") if isinstance(data, dict) else None
            raise E2EError(
                f"{method} {path}: expected HTTP {expected_status}, "
                f"received HTTP {status}; detail={detail!r}"
            )
        return status, data

    def _capture_cookies(self, headers: list[str]) -> None:
        for header in headers:
            parsed = SimpleCookie()
            parsed.load(header)
            for name, morsel in parsed.items():
                if morsel["max-age"] == "0" or not morsel.value:
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = morsel.value

    def login(self, email: str, password: str) -> str:
        _, data = self.request(
            "POST",
            "/api/auth/login",
            payload={"email": email, "password": password},
            expected_status=200,
        )
        if not isinstance(data, dict) or not isinstance(data.get("user"), dict):
            raise E2EError("Login did not return the expected public user profile")
        if "access_token" in data or "refresh_token" in data:
            raise E2EError("BFF exposed a bearer or refresh token in browser JSON")
        if ACCESS_COOKIE not in self.cookies or REFRESH_COOKIE not in self.cookies:
            raise E2EError("Login did not set both HttpOnly session cookies")
        return str(data["user"].get("id", ""))

    def current_user(self) -> dict:
        _, data = self.request(
            "GET", "/api/auth/me", expected_status=200
        )
        if not isinstance(data, dict) or not data.get("id"):
            raise E2EError("Authenticated profile response is malformed")
        return data


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise E2EError(f"Missing required CI environment value: {name}")
    return value


def run(base_url: str) -> None:
    email_a = _required_env("AQ_E2E_EMAIL_A")
    email_b = _required_env("AQ_E2E_EMAIL_B")
    password_a = _required_env("AQ_E2E_PASSWORD_A")
    password_b = _required_env("AQ_E2E_PASSWORD_B")

    owner_a = BrowserSession(base_url)
    owner_b = BrowserSession(base_url)

    user_a_id = owner_a.login(email_a, password_a)
    if not user_a_id or owner_a.current_user().get("id") != user_a_id:
        raise E2EError("Account A session did not resolve to the logged-in identity")
    old_refresh = owner_a.cookies[REFRESH_COOKIE]

    # Force the BFF through the real refresh endpoint without waiting for expiry.
    owner_a.cookies.pop(ACCESS_COOKIE, None)
    _, initial_conversations = owner_a.request(
        "GET", "/api/conversations", expected_status=200
    )
    if not isinstance(initial_conversations, list):
        raise E2EError("Account A conversation list is not an array")
    rotated_refresh = owner_a.cookies.get(REFRESH_COOKIE)
    if not rotated_refresh or rotated_refresh == old_refresh:
        raise E2EError("BFF did not persist the backend's rotated refresh ticket")
    if ACCESS_COOKIE not in owner_a.cookies:
        raise E2EError("BFF did not restore the access cookie after refresh")
    print("PASS: BFF login, HttpOnly cookies, and refresh-token rotation")

    _, created = owner_a.request(
        "POST",
        "/api/conversations",
        payload={"title": "Disposable staging isolation check", "mode": "normal"},
        expected_status=201,
    )
    if not isinstance(created, dict) or not created.get("id"):
        raise E2EError("Conversation creation returned no ID")
    conversation_id = str(created["id"])

    _, owner_list = owner_a.request(
        "GET", "/api/conversations", expected_status=200
    )
    if not isinstance(owner_list, list) or not any(
        isinstance(item, dict) and str(item.get("id")) == conversation_id
        for item in owner_list
    ):
        raise E2EError("Account A cannot read its own conversation")

    user_b_id = owner_b.login(email_b, password_b)
    if not user_b_id or user_b_id == user_a_id:
        raise E2EError("The two staging test identities are not distinct")
    if owner_b.current_user().get("id") != user_b_id:
        raise E2EError("Account B session did not resolve to the logged-in identity")

    _, other_list = owner_b.request(
        "GET", "/api/conversations", expected_status=200
    )
    if not isinstance(other_list, list) or any(
        isinstance(item, dict) and str(item.get("id")) == conversation_id
        for item in other_list
    ):
        raise E2EError("Cross-account conversation isolation failed")
    owner_b.request(
        "GET",
        f"/api/conversations/{conversation_id}/messages",
        expected_status=404,
    )
    print("PASS: two-account conversation ownership isolation")

    _, logout = owner_a.request(
        "POST", "/api/auth/logout", expected_status=200
    )
    if not isinstance(logout, dict) or logout.get("success") is not True:
        raise E2EError("Explicit logout did not confirm local and remote revocation")
    if ACCESS_COOKIE in owner_a.cookies or REFRESH_COOKIE in owner_a.cookies:
        raise E2EError("Logout did not clear both session cookies")
    owner_a.request("GET", "/api/auth/me", expected_status=401)
    owner_b.current_user()
    print("PASS: logout revokes Account A while Account B remains authenticated")
    print("FULLSTACK_STAGING_E2E=PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    try:
        base_url = _validate_loopback_origin(args.base_url)
        run(base_url)
    except (ValueError, E2EError) as error:
        print(f"FULLSTACK_STAGING_E2E=FAIL reason={error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
