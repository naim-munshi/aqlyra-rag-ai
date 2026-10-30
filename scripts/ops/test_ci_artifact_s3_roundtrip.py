"""CI S3 HTTP fixture safety guard: never touches providers in unit tests."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).with_name("ci_artifact_s3_roundtrip.py")
spec = importlib.util.spec_from_file_location("ci_artifact_s3_roundtrip", FILE)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

SAFE_DB = "postgresql+psycopg://postgres:postgres@localhost:5432/aqlyra_rag_ai"


class IsolatedS3GateTests(unittest.TestCase):
    def test_rejects_outside_github_ci(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": SAFE_DB, "GITHUB_ACTIONS": "false",
            "CI": "true",
        }):
            with self.assertRaises(smoke.CiS3Blocked):
                smoke.verify_disposable_scope()

    def test_rejects_any_remote_or_other_database(self):
        rejected = [
            "postgresql://postgres:passwd@ep-real.ap-southeast-1.aws.neon.tech/neondb",
            "postgresql://postgres:passwd@127.0.0.1:5432/neondb",
            "postgresql://neondb_owner:passwd@localhost:5432/aqlyra_rag_ai",
            "postgresql://postgres:passwd@localhost:5433/aqlyra_rag_ai",
            "postgresql://postgres:passwd@localhost/aqlyra_rag_ai#fragment",
            "https://example.invalid",
            "",
        ]
        for url in rejected:
            with self.subTest(class_of_url=url.split("://")[0]):
                with patch.dict(os.environ, {
                    "DATABASE_URL": url, "GITHUB_ACTIONS": "true",
                    "CI": "true",
                }):
                    with self.assertRaises(smoke.CiS3Blocked):
                        smoke.verify_disposable_scope()

    def test_allows_only_local_github_test_fixture(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": SAFE_DB, "GITHUB_ACTIONS": "true",
            "CI": "true",
        }):
            smoke.verify_disposable_scope()

    def test_refuses_state_outside_runner_temp_before_storage_client(self):
        with tempfile.TemporaryDirectory() as root:
            inside = Path(root) / "fixture-state.json"
            outside = Path(root).parent / "other-state.json"
            with patch.dict(os.environ, {
                "DATABASE_URL": SAFE_DB,
                "GITHUB_ACTIONS": "true",
                "CI": "true",
                "RUNNER_TEMP": root,
            }):
                with patch.object(smoke, "initialize", side_effect=AssertionError(
                    "storage must not be accessed"
                )):
                    with self.assertRaises(smoke.CiS3Blocked):
                        smoke.run("write", outside)
                link = Path(root) / "fake-state"
                link.symlink_to(outside)
                with patch.object(smoke, "initialize", side_effect=AssertionError(
                    "storage must not be accessed"
                )):
                    with self.assertRaises(smoke.CiS3Blocked):
                        smoke.run("write", link)
                # A safe path passes the validation and reaches the fake
                # initializer (but this test never contacts a server).
                with patch.object(smoke, "initialize", side_effect=RuntimeError(
                    "intentional no-network fixture"
                )):
                    with self.assertRaises(RuntimeError):
                        smoke.run("write", inside)


if __name__ == "__main__":
    unittest.main()
