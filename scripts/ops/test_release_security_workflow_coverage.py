"""Regression guard for the release-branch security workflow gap.

This test intentionally uses only the Python standard library so the
standalone operations gate can run without installing pytest or PyYAML.
It verifies workflow coverage, not GitHub ruleset enforcement.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def event_block(workflow: str, event: str) -> str:
    """Return one top-level GitHub Actions event block from YAML text."""
    match = re.search(
        rf"(?ms)^  {re.escape(event)}:\n(.*?)(?=^  (?:push|pull_request|workflow_dispatch|schedule):|\Z)",
        workflow,
    )
    if match is None:
        raise AssertionError(f"workflow is missing the {event!r} event")
    return match.group(1)


def covers_release_branch(event_yaml: str) -> bool:
    return re.search(r"""["']?release/\*\*["']?""", event_yaml) is not None


class ReleaseSecurityWorkflowCoverageTests(unittest.TestCase):
    def test_static_security_runs_for_release_pushes_and_pull_requests(self) -> None:
        workflow = (WORKFLOWS / "security-static.yml").read_text(encoding="utf-8")
        self.assertTrue(
            covers_release_branch(event_block(workflow, "push")),
            "Static Security Analysis must run when a release branch is pushed",
        )
        self.assertTrue(
            covers_release_branch(event_block(workflow, "pull_request")),
            "Static Security Analysis must run for PRs targeting release branches",
        )
        self.assertIn("bandit -r backend/app -q -lll", workflow)
        self.assertIn("frontend-security:", workflow)

    def test_dependency_audit_runs_for_release_pushes_and_pull_requests(self) -> None:
        workflow = (WORKFLOWS / "dependency-audit.yml").read_text(encoding="utf-8")
        self.assertTrue(
            covers_release_branch(event_block(workflow, "push")),
            "Dependency Security Audit must run when a release branch is pushed",
        )
        self.assertTrue(
            covers_release_branch(event_block(workflow, "pull_request")),
            "Dependency Security Audit must run for PRs targeting release branches",
        )
        self.assertIn("npm audit --omit=dev --audit-level=high", workflow)
        self.assertIn("pip-audit --no-deps --disable-pip -r backend/requirements.txt", workflow)
        self.assertIn("pip-audit --no-deps --disable-pip -r backend/requirements-voice.txt", workflow)

    def test_backend_ci_discovers_the_standalone_operations_tests(self) -> None:
        workflow = (WORKFLOWS / "backend-tests.yml").read_text(encoding="utf-8")
        self.assertIn("offline-ops-unittest:", workflow)
        self.assertIn("python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v", workflow)


if __name__ == "__main__":
    unittest.main()
