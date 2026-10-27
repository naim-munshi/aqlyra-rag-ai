#!/usr/bin/env python3
"""Fail-closed, read-only audit of a sanitized Railway staging inventory.

Input is a locally prepared JSON snapshot of Railway describe-environment
combined with describe-service for each service. Do not include variable
values or credentials. This gate is not a substitute for TLS or E2E testing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {"aqlyra-backend", "aqlyra-frontend", "aqlyra-postgres-pgvector", "aqlyra-redis"}
CORE_BRANCH = "release/core-without-study-abroad-20261027"
EXPECTED_REPO = "naim-munshi/aqlyra-rag-ai"
EXPECTED_ENV = "staging"

# Secrets are checked by key name only. This never reads/stores secrets.
REQUIRED_BACKEND_VARIABLE_NAMES = {
    "APP_ENV", "DEBUG", "SECRET_KEY", "DATABASE_URL",
    "REDIS_URL", "GOOGLE_CLIENT_ID", "SMTP_PASSWORD",
    "SMTP_HOST", "SMTP_USERNAME", "SMTP_FROM_EMAIL",
    "GROQ_API_KEY", "HF_TOKEN", "BROWSER_AGENT_ENABLED",
    "CORS_ORIGINS", "RATE_LIMIT_ENABLED", "RAG_GROUNDING_VERIFIER_ENABLED",
}
REQUIRED_FRONTEND_VARIABLE_NAMES = {"BACKEND_API_URL", "NEXT_PUBLIC_GOOGLE_CLIENT_ID"}


def assess(snapshot: dict, commit: str) -> list[str]:
    """Return structural blockers; all providers and HTTPS still need live tests."""
    errors: list[str] = []
    project = snapshot.get("project") or {}
    environment = snapshot.get("environment") or {}

    if project.get("name") != "Aqlyra-Staging":
        errors.append("Unexpected project; use Aqlyra-Staging only")
    if environment.get("name") != EXPECTED_ENV:
        errors.append("Unexpected environment; expected staging only")
    if snapshot.get("staged") is not None:
        errors.append("Pending/uncommitted Railway environment changes")
    services = snapshot.get("services") or []
    if not isinstance(services, list):
        return errors + ["Invalid service inventory"]
    by_name: dict[str, dict] = {}
    for item in services:
        name = item.get("name", "") if isinstance(item, dict) else ""
        if name in by_name:
            errors.append("Duplicate service name: " + name)
        if name:
            by_name[name] = item

    for missing in sorted(REQUIRED - set(by_name)):
        errors.append("Missing required service: " + missing)
    for name in sorted(REQUIRED & set(by_name)):
        item = by_name[name]
        if item.get("state") != "live":
            errors.append(name + " is not live")
        deployment = item.get("latestDeployment") or {}
        if deployment.get("status") != "SUCCESS":
            errors.append(name + " has no verified SUCCESS deployment")

    for name, mount in (("aqlyra-postgres-pgvector", "/var/lib/postgresql/data"),
                        ("aqlyra-backend", "/app/uploads")):
        item = by_name.get(name, {})
        volumes = item.get("volumes") or []
        if not any(
            isinstance(v, dict) and v.get("mountPath") == mount
            and v.get("state") == "live"
            for v in volumes
        ):
            errors.append(name + " lacks persistent volume at " + mount)

    postgres = by_name.get("aqlyra-postgres-pgvector", {})
    source = (postgres.get("config") or {}).get("source") or postgres.get("source") or {}
    if source.get("image") != "pgvector/pgvector:pg16":
        errors.append("PostgreSQL must run pinned pgvector/pgvector:pg16 image")

    for name in ("aqlyra-frontend", "aqlyra-backend"):
        item = by_name.get(name, {})
        cfg = item.get("config") or {}
        source = cfg.get("source") or item.get("source") or {}
        if source.get("repo") != EXPECTED_REPO:
            errors.append(name + " GitHub source does not match Aqlyra")
        if source.get("branch") != CORE_BRANCH:
            errors.append(name + " does not follow scoped core branch")
        if source.get("commitSha") != commit:
            errors.append(name + " is not pinned to expected commit")

    for name in ("aqlyra-backend", "aqlyra-redis", "aqlyra-postgres-pgvector"):
        item = by_name.get(name, {})
        domains = item.get("domains") or {}
        if domains.get("serviceDomains") or domains.get("customDomains"):
            errors.append(name + " must not expose HTTP public domain")
        if item.get("tcpProxies"):
            errors.append(name + " must not expose a public TCP proxy")

    frontend = by_name.get("aqlyra-frontend", {})
    domains = frontend.get("domains") or {}
    if not domains.get("serviceDomains") and not domains.get("customDomains"):
        errors.append("Frontend must have one private-test HTTPS origin")
    for name, required_vars in (
        ("aqlyra-backend", REQUIRED_BACKEND_VARIABLE_NAMES),
        ("aqlyra-frontend", REQUIRED_FRONTEND_VARIABLE_NAMES),
    ):
        actual = set((by_name.get(name) or {}).get("variableNames") or [])
        missing = required_vars - actual
        if missing:
            errors.append(name + " missing variable names: " + ", ".join(sorted(missing)))
    if "study-abroad" in " ".join(by_name.keys()).lower():
        errors.append("Study Abroad is deferred from the scoped release")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Sanitized, values-free Railway inventory JSON")
    parser.add_argument("--commit", required=True, help="Expected exact release commit SHA")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if len(args.commit) != 40 or any(c not in "0123456789abcdef" for c in args.commit):
        parser.error("--commit requires an exact lowercase 40-digit SHA")
    try:
        payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object")
        failures = assess(payload, args.commit)
    except (OSError, ValueError, UnicodeError) as exc:
        failures = ["Railway inventory missing or invalid: " + type(exc).__name__]
    result = {"staging_structural_gate": "BLOCKED" if failures else "PASS",
              "live_https_and_provider_acceptance": "NOT_CHECKED", "failures": failures}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("RAILWAY_STAGING_GATE=" + result["staging_structural_gate"])
        for problem in failures:
            print("BLOCKER: " + problem)
        print("Real HTTPS, SMTP, Google OAuth and LLM/RAG tests require separate evidence")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
