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
    "Static Security Analysis",
})


CHECK_CONTEXTS = frozenset({
    "Python 3.13 / PostgreSQL 16",
    "Frontend lint, typecheck and build",
    "Validate staging smoke contracts",
    "Validate production Compose configuration",
    "Build production Docker images",
    "Native ARM64 builds + real local reverse-proxy smoke",
    "npm security audit",
    "Python security audit",
    "Check Markdown links and code fences",
    "Always-on Merge Gate",
    "High-severity Python SAST",
})

def github_api(path: str) -> dict | list:
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
    if not isinstance(result, (dict, list)):
        raise ValueError("Unexpected GitHub API response")
    return result


def verified_main_ruleset(rulesets: list[dict]) -> bool:
    """Require enforced default-branch reviews, status checks and ref safety."""
    for ruleset in rulesets:
        if not isinstance(ruleset, dict):
            continue
        if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
            continue
        refs = (ruleset.get("conditions") or {}).get("ref_name") or {}
        includes = set(refs.get("include") or [])
        excludes = set(refs.get("exclude") or [])
        targets = {"refs/heads/main", "~DEFAULT_BRANCH", "~ALL"}
        if not includes.intersection(targets) or excludes.intersection(targets):
            continue
        rules = {
            rule.get("type"): rule for rule in (ruleset.get("rules") or [])
            if isinstance(rule, dict) and isinstance(rule.get("type"), str)
        }
        if not {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}.issubset(rules):
            continue
        reviews = (rules["pull_request"].get("parameters") or {}).get(
            "required_approving_review_count", 0
        )
        if not isinstance(reviews, int) or reviews < 1:
            continue
        checks = (rules["required_status_checks"].get("parameters") or {}).get(
            "required_status_checks", []
        )
        contexts = {
            item.get("context") for item in checks
            if isinstance(item, dict) and isinstance(item.get("context"), str)
        }
        if CHECK_CONTEXTS.issubset(contexts):
            return True
    return False


def evaluate(
    main: dict, release: dict, runs: dict, rulesets: list[dict] | None = None
) -> tuple[bool, list[str], str]:
    errors: list[str] = []
    sha = release.get("commit", {}).get("sha", "")
    if not isinstance(sha, str) or len(sha) != 40:
        errors.append("Release branch HEAD is unknown")
        sha = ""
    if main.get("protected") is not True:
        errors.append("main is NOT branch protected: enforce required reviews and checks")
    if not verified_main_ruleset(rulesets or []):
        errors.append(
            "No verified active main ruleset enforcing reviews, all required "
            "job checks, deletion and force-push restrictions"
        )
    if main.get("commit", {}).get("sha") == sha:
        errors.append("Release branch points to main; review the intended candidate")

    raw_runs = runs.get("workflow_runs", [])
    if not isinstance(raw_runs, list):
        errors.append("GitHub workflow response is invalid")
        raw_runs = []
    current_runs = [
        run for run in raw_runs
        if isinstance(run, dict)
        and run.get("head_sha") == sha
        and run.get("name") in REQUIRED
    ]
    # GitHub returns newest first, but sort by run/attempt metadata to
    # prevent an older successful execution hiding a newer failure.
    current_runs.sort(
        key=lambda run: (
            int(run.get("run_number") or 0),
            int(run.get("run_attempt") or 0),
            str(run.get("created_at") or ""),
            int(run.get("id") or 0),
        ),
        reverse=True,
    )
    latest = {}
    for run in current_runs:
        latest.setdefault(run["name"], run)
    successful = {
        name for name, run in latest.items()
        if run.get("status") == "completed" and run.get("conclusion") == "success"
    }
    missing = sorted(REQUIRED - successful)
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
        summaries = github_api("/rulesets")
        if not isinstance(summaries, list):
            raise ValueError("Invalid rulesets response")
        rulesets = [
            github_api("/rulesets/" + str(item["id"]))
            for item in summaries
            if isinstance(item, dict)
            and item.get("target") == "branch"
            and item.get("enforcement") == "active"
            and isinstance(item.get("id"), int)
        ]
        if not all(isinstance(item, dict) for item in rulesets):
            raise ValueError("Invalid ruleset details")
        if not isinstance(main_data, dict) or not isinstance(release_data, dict) or not isinstance(run_data, dict):
            raise ValueError("Invalid GitHub metadata")
        ok, errors, sha = evaluate(main_data, release_data, run_data, rulesets)
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
