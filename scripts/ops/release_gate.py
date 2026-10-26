#!/usr/bin/env python3
"""Read-only release gate for naim-munshi/aqlyra-rag-ai.

Automation proves only the exact GitHub commit/check status and branch
protection. Manual staging and real-provider acceptance is deliberately
outside this script: do not interpret success as permission to deploy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "naim-munshi/aqlyra-rag-ai"
RELEASE_BRANCH = "integration/security-release-candidate-20261026"
REQUIRED = frozenset({
    "Backend Tests",
    "Frontend and Deployment Checks",
    "Dependency Security Audit",
    "Native ARM64 Full-stack Predeploy",
    "Documentation Consistency",
    "Always-on Merge Gate",
})


def github_api(path: str) -> dict:
    """Access only canonical GitHub API resources, never user-supplied URLs."""
    url = "https://api.github.com/repos/" + REPO + path
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Aqlyra-Release-Gate/1.0",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("Unexpected GitHub API response")
    return result


def evaluate(main: dict, release: dict, runs: dict) -> tuple[bool, list[str], str]:
    errors: list[str] = []
    sha = release.get("commit", {}).get("sha", "")
    if not isinstance(sha, str) or len(sha) != 40:
        errors.append("Release branch HEAD is unknown")
        sha = ""
    if main.get("protected") is not True:
        errors.append("main is NOT branch protected: enforce required reviews and checks")
    if main.get("commit", {}).get("sha") == sha:
        errors.append("Release branch points to main; review the intended candidate")

    checks = {}
    raw_runs = runs.get("workflow_runs", [])
    if not isinstance(raw_runs, list):
        errors.append("GitHub workflow response is invalid")
        raw_runs = []
    for run in raw_runs:
        if not isinstance(run, dict) or run.get("head_sha") != sha:
            continue
        name = run.get("name")
        if name not in REQUIRED:
            continue
        # Multiple workflow attempts/reruns can exist; only completed successes
        # of the exact HEAD satisfy the check.
        if run.get("status") == "completed" and run.get("conclusion") == "success":
            checks[name] = True
        else:
            checks.setdefault(name, False)

    missing = sorted(REQUIRED - {name for name, passed in checks.items() if passed})
    if missing:
        errors.append("Required CI not green for exact HEAD: " + ", ".join(missing))

    return not errors, errors, sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable result")
    args = parser.parse_args(argv)
    try:
        main_data = github_api("/branches/main")
        release_data = github_api("/branches/" + quote(RELEASE_BRANCH, safe="/"))
        run_data = github_api(
            "/actions/runs?branch=" + quote(RELEASE_BRANCH, safe="")
            + "&per_page=100"
        )
        ok, errors, sha = evaluate(main_data, release_data, run_data)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError) as exc:
        ok, errors, sha = False, ["GitHub verification unavailable: " + type(exc).__name__], ""
    report = {
        "repository": REPO,
        "release_branch": RELEASE_BRANCH,
        "head_sha": sha,
        "automated_gate_passed": ok,
        "production_approved": False,
        "errors": errors,
        "manual_approval_required": [
            "Owner approval and enforced main branch ruleset",
            "Real HTTPS staging with Google, SMTP, LLM and embeddings",
            "DB migrations verified on a restored disposable dataset",
            "Cross-tenant auth/RAG and consent tests with real providers",
            "Browser and artifact worker isolation and off-host encrypted backup",
            "Study Abroad official-source review and multilingual export QA",
        ],
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("AQLYRA_AUTOMATED_RELEASE_GATE=" + ("PASS" if ok else "BLOCKED"))
        print("HEAD=" + (sha or "unverified"))
        for error in errors:
            print("BLOCKER: " + error)
        print("PRODUCTION_APPROVED=false (manual gates are not automatic)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
