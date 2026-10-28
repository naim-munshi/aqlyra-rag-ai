"""Offline safety regressions for CI-only original-document S3 rehearsal.

No real S3 client, remote request, Neon database or user file is opened.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("ci_private_document_s3_roundtrip.py")
spec = importlib.util.spec_from_file_location("ci_private_document_s3", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OriginalDocumentS3SafetyTest(unittest.TestCase):
    def test_source_only_allows_loopback_and_mock_credentials(self):
        self.assertEqual(module.ENDPOINT, "http://127.0.0.1:5000")
        self.assertNotIn("neondb_owner", module.CONTENT.decode("utf-8"))
        self.assertIn("synthetic", module.CONTENT.decode("utf-8"))
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("verify_disposable_scope()", script)
        self.assertNotIn("AWS_ACCESS_KEY_ID=os.environ", script)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY=os.environ", script)

    def test_ci_guard_denies_nonlocal_database(self):
        dbs = [
            "postgresql://postgres:safe@ep-other.aws.neon.tech/neondb",
            "postgresql://postgres:fake@localhost/neondb",
            "postgresql://different:fake@localhost/aqlyra_rag_ai",
        ]
        for db in dbs:
            with self.subTest(database_kind=db.split("@")[-1]):
                with patch.dict(os.environ, {
                    "GITHUB_ACTIONS": "true", "CI": "true",
                    "DATABASE_URL": db,
                }):
                    with self.assertRaises(ValueError):
                        module.verify_disposable_scope()

    def test_outside_runner_temp_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            within = Path(root) / "state.json"
            outside = Path(root).parent / "never-create-state.json"
            link = Path(root) / "link.json"
            link.symlink_to(outside)
            with patch.dict(os.environ, {"RUNNER_TEMP": root}):
                module.check_state_path(within)
                for path in (outside, link):
                    with self.subTest(path=path.name):
                        with self.assertRaises(module.PrivateS3RehearsalBlocked):
                            module.check_state_path(path)

    def test_non_ci_run_never_calls_client(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "original.json"
            with patch.dict(os.environ, {
                "GITHUB_ACTIONS": "false", "CI": "true",
                "DATABASE_URL": (
                    "postgresql://postgres:fake@localhost/aqlyra_rag_ai"
                ),
                "RUNNER_TEMP": root,
            }), patch.object(
                module, "client_and_cfg",
                side_effect=AssertionError("must not contact S3"),
            ):
                code = module.main(["--phase", "write", "--state-file", str(path)])
            self.assertEqual(code, 2)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
