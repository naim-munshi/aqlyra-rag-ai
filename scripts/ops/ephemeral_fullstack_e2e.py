#!/usr/bin/env python3
"""Cost-free, disposable CI-only full-stack backend E2E acceptance.

Tests actual HTTP -> FastAPI -> PostgreSQL/pgvector -> RAG processing for
two synthetic users. NEVER run against production, real staging accounts,
or an external host: URLs must be loopback; CI-only email bypass required.
No private data or tokens are printed. No third-party provider is used.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class BlockRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Result:
    status: int
    payload: object
    body: bytes


class SmokeFailure(Exception):
    pass


def safe_url(raw: str) -> str:
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query or parsed.fragment
        or parsed.port != 8000
    ):
        raise ValueError("Only http://127.0.0.1:8000 is permitted for disposable CI")
    return "http://127.0.0.1:8000"


class Client:
    def __init__(self, origin: str):
        self.origin = safe_url(origin)
        self.opener = build_opener(BlockRedirect())

    def request(
        self, method: str, path: str, *, token: str | None = None,
        data: dict | None = None,
        upload: tuple[str, bytes] | None = None,
    ) -> Result:
        if not path.startswith("/api/v1/") or "//" in path or ".." in path:
            raise SmokeFailure("Unexpected API route")
        headers = {"Cache-Control": "no-store"}
        body = None
        if token:
            headers["Authorization"] = "Bearer " + token
        if data is not None and upload is not None:
            raise SmokeFailure("Ambiguous HTTP body")
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if upload is not None:
            filename, contents = upload
            if filename != "ci-tenant-evidence.md" or len(contents) > 8192:
                raise SmokeFailure("Unexpected upload payload")
            boundary = "aqlyraci" + secrets.token_hex(12)
            body = (
                ("--" + boundary + "\r\n"
                 'Content-Disposition: form-data; name="file"; '
                 'filename="ci-tenant-evidence.md"\r\n'
                 "Content-Type: text/markdown\r\n\r\n").encode("ascii")
                + contents + ("\r\n--" + boundary + "--\r\n").encode("ascii")
            )
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary

        req = Request(self.origin + path, data=body, headers=headers, method=method)
        try:
            res = self.opener.open(req, timeout=30)
        except HTTPError as exc:
            res = exc
        with res:
            status = res.status
            content = res.read(1048577)
            kind = res.headers.get("Content-Type", "").split(";")[0].strip()
        if len(content) > 1048576:
            raise SmokeFailure("Unexpected HTTP response size at " + path)
        payload: object = None
        if kind == "application/json" and content:
            try:
                payload = json.loads(content)
            except ValueError as exc:
                raise SmokeFailure("Invalid JSON at " + path) from exc
        return Result(status=status, payload=payload, body=content)


def expect(result: Result, status: int, stage: str) -> dict:
    if result.status != status:
        raise SmokeFailure(
            stage + " expected HTTP " + str(status)
            + ", got HTTP " + str(result.status)
        )
    if status in (200, 201) and not isinstance(result.payload, dict):
        raise SmokeFailure(stage + " returned unexpected response")
    return result.payload if isinstance(result.payload, dict) else {}


def create_account(client: Client, tag: str) -> tuple[str, str]:
    suffix = secrets.token_hex(7)
    identity = {
        "username": "cismoke" + tag + suffix,
        "email": "cismoke-" + tag + "-" + suffix + "@example.com",
        "password": "CI-only-" + secrets.token_urlsafe(23) + "!",
    }
    registration = expect(
        client.request("POST", "/api/v1/auth/register", data=identity),
        201, "synthetic registration",
    )
    if registration.get("verification_required") is not False:
        raise SmokeFailure("Synthetic CI-only email verification bypass is not enabled")
    login = expect(client.request(
        "POST", "/api/v1/auth/login",
        data={"email": identity["email"], "password": identity["password"]},
    ), 200, "synthetic login")
    token = login.get("access_token")
    if not isinstance(token, str) or len(token) < 10:
        raise SmokeFailure("Synthetic login omitted token")
    profile = expect(
        client.request("GET", "/api/v1/users/me", token=token),
        200, "authenticated profile",
    )
    user_id = profile.get("id")
    if not isinstance(user_id, str):
        raise SmokeFailure("Synthetic profile missing id")
    return token, user_id


def run(client: Client) -> None:
    expect(client.request("GET", "/api/v1/health"), 200, "backend health")
    expect(client.request("GET", "/api/v1/users/me"), 401, "anonymous auth")
    expect(client.request(
        "POST", "/api/v1/rag/answer",
        data={"question": "private question"},
    ), 401, "anonymous RAG")
    workflows = client.request("GET", "/api/v1/study-abroad/workflows")
    if workflows.status != 200 or not isinstance(workflows.payload, list):
        raise SmokeFailure("Study Abroad workflows are unavailable")
    choices = {
        item.get("id"): item for item in workflows.payload
        if isinstance(item, dict)
    }
    if choices.get("student", {}).get("enabled") is not True:
        raise SmokeFailure("Student study-abroad workflow is disabled")
    if choices.get("job", {}).get("enabled") is not False:
        raise SmokeFailure("Unreviewed work-visa workflow must stay disabled")
    expect(client.request(
        "GET", "/api/v1/study-abroad/cases",
    ), 401, "anonymous Study Abroad data access")
    print("PASS security baseline and registered Study Abroad workflows")

    token_a, id_a = create_account(client, "a")
    token_b, id_b = create_account(client, "b")
    if id_a == id_b:
        raise SmokeFailure("Synthetic identities are not distinct")
    print("PASS two-user registration, login and verified identities")

    study_case = expect(client.request(
        "POST", "/api/v1/study-abroad/cases", token=token_a,
        data={
            "workflow": "student",
            "nationality": "Bangladesh",
            "residence_country": "Japan",
            "destination_country": "Germany",
            "degree_level": "Master's",
            "study_field": "Computer Science",
            "intake": "Winter 2027",
        },
    ), 201, "create private Study Abroad case")
    study_id = study_case.get("id")
    if not isinstance(study_id, str):
        raise SmokeFailure("Study Abroad case has no id")
    expect(client.request(
        "GET", "/api/v1/study-abroad/cases/" + study_id,
        token=token_b,
    ), 404, "cross-account Study Abroad case isolation")
    own_case = expect(client.request(
        "GET", "/api/v1/study-abroad/cases/" + study_id,
        token=token_a,
    ), 200, "owner Study Abroad case")
    if own_case.get("nationality") != "Bangladesh":
        raise SmokeFailure("Study Abroad case data did not persist")
    print("PASS private Study Abroad creation and cross-user isolation")

    conv = expect(client.request(
        "POST", "/api/v1/conversations", token=token_a,
        data={"title": "CI private RAG", "mode": "knowledge"},
    ), 201, "private conversation")
    conversation_id = conv.get("id")
    if not isinstance(conversation_id, str):
        raise SmokeFailure("Missing private conversation id")
    expect(client.request(
        "GET", "/api/v1/conversations/" + conversation_id, token=token_b,
    ), 404, "cross-user conversation lookup")
    print("PASS account-scoped conversation isolation")

    evidence = (
        "# Authentication\n\n"
        "JWT bearer tokens protect private API routes and "
        "prevent other accounts from reading their documents. "
        "Aqlyra evidence is checked with citations.\n"
    ).encode("utf-8")
    document = expect(client.request(
        "POST", "/api/v1/documents/upload", token=token_a,
        upload=("ci-tenant-evidence.md", evidence),
    ), 201, "private document upload")
    document_id = document.get("id")
    if not isinstance(document_id, str):
        raise SmokeFailure("Missing private document id")
    processed = expect(client.request(
        "POST", "/api/v1/documents/" + document_id + "/process",
        token=token_a,
    ), 200, "document parsing/embedding")
    if processed.get("status") != "ready":
        raise SmokeFailure("Private document did not reach ready status")
    own_content = client.request(
        "GET", "/api/v1/documents/" + document_id + "/content",
        token=token_a,
    )
    if own_content.status != 200 or b"JWT bearer tokens" not in own_content.body:
        raise SmokeFailure("Owner cannot read their own persisted file")
    expect(client.request(
        "GET", "/api/v1/documents/" + document_id + "/content",
        token=token_b,
    ), 404, "cross-user private file isolation")
    expect(client.request(
        "GET", "/api/v1/documents/" + document_id,
        token=token_b,
    ), 404, "cross-user document metadata")
    linked_study = expect(client.request(
        "POST", "/api/v1/study-abroad/cases/" + study_id + "/documents",
        token=token_a,
        data={"document_id": document_id, "checklist_key": "academic"},
    ), 201, "owner Study Abroad document linkage")
    if linked_study.get("document_id") != document_id:
        raise SmokeFailure("Study Abroad linkage changed document identity")
    expect(client.request(
        "GET", "/api/v1/study-abroad/cases/" + study_id + "/documents",
        token=token_b,
    ), 404, "cross-user Study Abroad document scope")
    print("PASS Study Abroad owner-scoped ready-document linkage")
    print("PASS upload -> persistent file -> parsing -> pgvector embedding")

    question = "JWT bearer tokens protect private API routes"
    result = expect(client.request(
        "POST", "/api/v1/retrieval/search", token=token_a,
        data={"query": question, "top_k": 5,
              "chunk_roles": ["content"], "document_ids": [document_id]},
    ), 200, "owner retrieval")
    items = result.get("items")
    if not isinstance(items, list) or not items or not all(
        x.get("document_id") == document_id for x in items
        if isinstance(x, dict)
    ):
        raise SmokeFailure("Owner could not retrieve only their own evidence")
    other = expect(client.request(
        "POST", "/api/v1/retrieval/search", token=token_b,
        data={"query": question, "top_k": 5, "document_ids": [document_id]},
    ), 200, "cross-user retrieval")
    if other.get("total") != 0 or other.get("items") != []:
        raise SmokeFailure("Cross-user private retrieval leaked results")
    print("PASS live DB-backed retrieval and tenant isolation")

    answer = expect(client.request(
        "POST", "/api/v1/rag/answer", token=token_a,
        data={"question": question, "top_k": 5, "document_ids": [document_id],
              "chunk_roles": ["content"], "min_similarity": -1.0},
    ), 200, "owner grounded RAG")
    citations = answer.get("citations", [])
    if (answer.get("is_refusal") is not False
            or not isinstance(citations, list) or not citations
            or any(c.get("document_id") != document_id for c in citations)):
        raise SmokeFailure("Grounded answer lacks owner-scoped valid citations")
    denied = expect(client.request(
        "POST", "/api/v1/rag/answer", token=token_b,
        data={"question": question, "top_k": 5, "document_ids": [document_id]},
    ), 200, "cross-user RAG")
    if denied.get("is_refusal") is not True or denied.get("citations") != []:
        raise SmokeFailure("Cross-user RAG failed safe refusal")
    print("PASS deterministic RAG citations and refusal across two tenants")
    print("EPHEMERAL_E2E=PASS (no real providers / HTTPS / persistent staging)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000",
        help="Disposable loopback FastAPI origin; external hosts are forbidden",
    )
    args = parser.parse_args(argv)
    try:
        run(Client(args.base_url))
    except (SmokeFailure, OSError, ValueError, TimeoutError) as exc:
        print("EPHEMERAL_E2E=FAIL: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
