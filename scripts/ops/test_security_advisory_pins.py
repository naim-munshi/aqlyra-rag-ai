"""Regression guard for 2026-11-02 audit-confirmed, pinned dependency advisories.

This is only a lockfile/pin contract. Security advisories are independently
enforced by npm audit and pip-audit in the GitHub dependency-audit workflow.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def versions(text):
    return tuple(int(v) for v in text.split("."))


class SecurityAdvisoryPinTests(unittest.TestCase):
    def test_next_and_linter_are_patched_and_locked(self):
        package = json.loads((ROOT / "frontend/package.json").read_text())
        lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
        actual = package["dependencies"]["next"]
        eslint = package["devDependencies"]["eslint-config-next"]
        self.assertGreaterEqual(versions(actual), (16, 4, 1))
        self.assertEqual(actual, eslint)
        self.assertEqual(lock["packages"][""]["dependencies"]["next"], actual)
        self.assertEqual(
            lock["packages"][""]["devDependencies"]["eslint-config-next"],
            eslint,
        )
        for key in (
            "node_modules/next",
            "node_modules/eslint-config-next",
            "node_modules/@next/env",
            "node_modules/@next/eslint-plugin-next",
            "node_modules/@next/swc-linux-x64-gnu",
            "node_modules/@next/swc-linux-arm64-gnu",
        ):
            self.assertEqual(lock["packages"][key]["version"], actual)

    def test_pip_audit_confirmed_python_packages_are_patched(self):
        requirements = (ROOT / "backend/requirements.txt").read_text()
        pinned = {}
        for line in requirements.splitlines():
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)+)", line)
            if match:
                name = match.group(1).lower().replace("_", "-")
                self.assertNotIn(name, pinned)
                pinned[name] = versions(match.group(2))

        minimums = {
            "certifi": (2026, 10, 18),
            "aiohttp": (3, 14, 4),
            "yarl": (1, 25, 1),
            "dnspython": (2, 9, 0),
            "filelock": (4, 2, 1),
            "langgraph": (1, 2, 14),
            "langgraph-sdk": (0, 4, 6),
            "pillow": (13, 0, 0),
            "pyasn1": (0, 6, 5),
            "pypdf": (6, 21, 4),
        }
        for name, minimum in minimums.items():
            with self.subTest(package=name):
                self.assertIn(name, pinned)
                self.assertGreaterEqual(pinned[name], minimum)


if __name__ == "__main__":
    unittest.main()
