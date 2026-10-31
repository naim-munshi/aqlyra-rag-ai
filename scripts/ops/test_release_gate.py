"""Offline checks for the Aqlyra release decision gate."""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).with_name("release_gate.py")
spec = importlib.util.spec_from_file_location("aqlyra_release_gate", path)
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.main = {"protected": True, "commit": {"sha": "b" * 40}}
        self.release = {"commit": {"sha": self.sha}}
        self.rulesets = [{
            "target": "branch",
            "enforcement": "active",
            "conditions": {
                "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
            },
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "pull_request", "parameters": {
                    "required_approving_review_count": 1
                }},
                {"type": "required_status_checks", "parameters": {
                    "required_status_checks": [
                        {"context": context} for context in gate.CHECK_CONTEXTS
                    ]
                }},
            ],
        }]
        self.runs = {
            "workflow_runs": [
                {
                    "head_sha": self.sha,
                    "name": name,
                    "status": "completed",
                    "conclusion": "success",
                }
                for name in gate.REQUIRED
            ]
        }

    def test_exact_sha_green_with_protected_main_passes_automated_gate(self):
        ok, issues, sha = gate.evaluate(self.main, self.release, self.runs, self.rulesets)
        self.assertTrue(ok)
        self.assertEqual(issues, [])
        self.assertEqual(sha, self.sha)

    def test_semantic_worker_is_mandatory_for_release_even_if_other_ci_passes(self):
        self.assertIn("Isolated Semantic Worker Acceptance", gate.REQUIRED)
        worker = next(
            run for run in self.runs["workflow_runs"]
            if run["name"] == "Isolated Semantic Worker Acceptance"
        )
        worker["conclusion"] = "failure"
        ok, issues, _ = gate.evaluate(
            self.main, self.release, self.runs, self.rulesets
        )
        self.assertFalse(ok)
        self.assertTrue(any("Isolated Semantic Worker Acceptance" in err for err in issues))

    def test_unprotected_main_fails_even_with_all_checks_green(self):
        self.main["protected"] = False
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs, self.rulesets)
        self.assertFalse(ok)
        self.assertTrue(any("NOT branch protected" in x for x in errors))

    def test_old_commit_successes_cannot_bypass_failed_current_head(self):
        self.runs["workflow_runs"].pop()
        self.runs["workflow_runs"].append({
            "head_sha": "c" * 40,
            "name": next(iter(gate.REQUIRED)),
            "status": "completed",
            "conclusion": "success",
        })
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs, self.rulesets)
        self.assertFalse(ok)
        self.assertTrue(any("Required CI not green" in x for x in errors))

    def test_unknown_branch_head_and_missing_status_fail_closed(self):
        self.release["commit"]["sha"] = "bad"
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs, self.rulesets)
        self.assertFalse(ok)
        self.assertTrue(any("HEAD is unknown" in x for x in errors))

    def test_incomplete_or_cancelled_check_is_never_accepted(self):
        self.runs["workflow_runs"][0]["status"] = "in_progress"
        self.runs["workflow_runs"][0]["conclusion"] = None
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs, self.rulesets)
        self.assertFalse(ok)
        self.assertTrue(any("Required CI not green" in x for x in errors))

    def test_protected_flag_without_approved_ruleset_is_not_enough(self):
        self.rulesets = []
        ok, errors, _ = gate.evaluate(
            self.main, self.release, self.runs, self.rulesets
        )
        self.assertFalse(ok)
        self.assertTrue(any("No verified active main ruleset" in x for x in errors))

    def test_ruleset_without_required_job_or_force_push_protection_fails(self):
        self.rulesets[0]["rules"].pop(1)  # non_fast_forward
        ok, _, _ = gate.evaluate(
            self.main, self.release, self.runs, self.rulesets
        )
        self.assertFalse(ok)

        self.rulesets[0]["rules"].insert(1, {"type": "non_fast_forward"})
        checks = self.rulesets[0]["rules"][3]["parameters"]["required_status_checks"]
        checks.pop()
        ok, _, _ = gate.evaluate(
            self.main, self.release, self.runs, self.rulesets
        )
        self.assertFalse(ok)

    def test_old_green_attempt_cannot_hide_newer_failed_run(self):
        name = self.runs["workflow_runs"][0]["name"]
        self.runs["workflow_runs"][0]["run_number"] = 7
        self.runs["workflow_runs"].append({
            "head_sha": self.sha, "name": name, "run_number": 8,
            "status": "completed", "conclusion": "failure",
        })
        ok, errors, _ = gate.evaluate(
            self.main, self.release, self.runs, self.rulesets
        )
        self.assertFalse(ok)
        self.assertTrue(any("Required CI not green" in x for x in errors))

    def test_release_gate_defaults_to_scoped_core_branch(self):
        self.assertEqual(
            gate.RELEASE_BRANCH,
            "release/core-without-study-abroad-20261027",
        )

    def test_cli_respects_candidate_branch_and_uses_exact_sha(self):
        from unittest.mock import patch
        import contextlib
        import io
        import json

        calls = []

        def mocked_github_api(path):
            calls.append(path)
            if path == "/branches/main":
                return self.main
            if path == "/branches/release-candidate-test":
                return self.release
            if path == "/actions/runs?branch=release-candidate-test&per_page=100":
                return self.runs
            if path == "/rulesets":
                return [{"id": 42, "target": "branch", "enforcement": "active"}]
            if path == "/rulesets/42":
                return self.rulesets[0]
            raise AssertionError("Unexpected API path: " + path)

        stream = io.StringIO()
        with patch.object(gate, "github_api", side_effect=mocked_github_api):
            with contextlib.redirect_stdout(stream):
                result = gate.main([
                    "--json", "--release-branch", "release-candidate-test"
                ])
        report = json.loads(stream.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(report["release_branch"], "release-candidate-test")
        self.assertEqual(report["head_sha"], self.sha)
        self.assertTrue(report["automated_gate_passed"])
        self.assertFalse(report["production_approved"])
        self.assertIn(
            "/actions/runs?branch=release-candidate-test&per_page=100",
            calls,
        )

    def test_branch_specific_ruleset_does_not_protect_main(self):
        self.rulesets[0]["conditions"]["ref_name"]["include"] = [
            "refs/heads/development"
        ]
        ok, _, _ = gate.evaluate(
            self.main, self.release, self.runs, self.rulesets
        )
        self.assertFalse(ok)



if __name__ == "__main__":
    unittest.main()
