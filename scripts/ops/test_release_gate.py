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
        ok, issues, sha = gate.evaluate(self.main, self.release, self.runs)
        self.assertTrue(ok)
        self.assertEqual(issues, [])
        self.assertEqual(sha, self.sha)

    def test_unprotected_main_fails_even_with_all_checks_green(self):
        self.main["protected"] = False
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs)
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
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs)
        self.assertFalse(ok)
        self.assertTrue(any("Required CI not green" in x for x in errors))

    def test_unknown_branch_head_and_missing_status_fail_closed(self):
        self.release["commit"]["sha"] = "bad"
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs)
        self.assertFalse(ok)
        self.assertTrue(any("HEAD is unknown" in x for x in errors))

    def test_incomplete_or_cancelled_check_is_never_accepted(self):
        self.runs["workflow_runs"][0]["status"] = "in_progress"
        self.runs["workflow_runs"][0]["conclusion"] = None
        ok, errors, _ = gate.evaluate(self.main, self.release, self.runs)
        self.assertFalse(ok)
        self.assertTrue(any("Required CI not green" in x for x in errors))


if __name__ == "__main__":
    unittest.main()
