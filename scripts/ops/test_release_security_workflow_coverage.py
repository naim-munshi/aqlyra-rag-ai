"""Regression guard for release-branch workflow coverage.

Uses only the Python standard library. It verifies workflow trigger coverage,
not GitHub ruleset enforcement or real production staging.
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
        self.assertTrue(covers_release_branch(event_block(workflow, "push")))
        self.assertTrue(covers_release_branch(event_block(workflow, "pull_request")))
        self.assertIn("bandit -r backend/app -q -lll", workflow)
        self.assertIn("frontend-security:", workflow)
        self.assertIn("name: Frontend CSRF, XSS and proxy security regression", workflow)

    def test_dependency_audit_runs_for_release_pushes_and_pull_requests(self) -> None:
        workflow = (WORKFLOWS / "dependency-audit.yml").read_text(encoding="utf-8")
        self.assertTrue(covers_release_branch(event_block(workflow, "push")))
        self.assertTrue(covers_release_branch(event_block(workflow, "pull_request")))
        self.assertIn("npm audit --omit=dev --audit-level=high", workflow)
        self.assertIn("pip-audit --no-deps --disable-pip -r backend/requirements.txt", workflow)
        self.assertIn("pip-audit --no-deps --disable-pip -r backend/requirements-voice.txt", workflow)

    def test_all_release_preflight_checks_run_for_release_pushes_and_prs(self) -> None:
        release_workflows = (
            "frontend-deployment.yml",
            "arm64-predeploy.yml",
            "documentation.yml",
            "merge-gate.yml",
        )
        for filename in release_workflows:
            workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
            for event in ("push", "pull_request"):
                with self.subTest(workflow=filename, event=event):
                    self.assertTrue(
                        covers_release_branch(event_block(workflow, event)),
                        f"{filename} must trigger on {event} for release/**",
                    )

    def test_backend_ci_discovers_standalone_operations_tests(self) -> None:
        workflow = (WORKFLOWS / "backend-tests.yml").read_text(encoding="utf-8")
        self.assertIn("offline-ops-unittest:", workflow)
        self.assertIn("postgres-version: [16, 18]", workflow)
        self.assertIn(
            "python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
