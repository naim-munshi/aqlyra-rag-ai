"""Offline security regression tests: production DB isolation checks never write."""
import importlib.util
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

source = Path(__file__).with_name("production_db_isolation_gate.py")
spec = importlib.util.spec_from_file_location("aqlyra_db_isolation_gate", source)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HOST = "ep-test.aws-ap-southeast-1.neon.tech"
RUNTIME = "aqlyra_runtime"
VALID_URL = (
    f"postgresql://{RUNTIME}:private-do-not-print@{HOST}/neondb?sslmode=require"
)


def catalog(*, rls=True, owner="neondb_owner", policies=1):
    return [(table, rls, owner, policies) for table in gate.TENANT_TABLES]


class DatabaseIsolationGateTests(unittest.TestCase):
    def test_catalog_requires_every_table_rls_and_policy(self):
        self.assertEqual(
            gate.evaluate_catalog(RUNTIME, (False, False), catalog(),
                                  gate.EXPECTED_REVISION), []
        )
        missing_rls = gate.evaluate_catalog(
            RUNTIME, (False, False), catalog(rls=False), gate.EXPECTED_REVISION
        )
        self.assertTrue(any(":rls_disabled" in item for item in missing_rls))
        no_policies = gate.evaluate_catalog(
            RUNTIME, (False, False), catalog(policies=0), gate.EXPECTED_REVISION
        )
        self.assertTrue(any(":no_policy" in item for item in no_policies))

    def test_owner_and_superuser_bypass_are_blocked(self):
        for flags in ((True, False), (False, True)):
            with self.subTest(flags=flags):
                errors = gate.evaluate_catalog(
                    RUNTIME, flags, catalog(), gate.EXPECTED_REVISION
                )
                self.assertIn("runtime_role_bypasses_rls", errors)
        errors = gate.evaluate_catalog(
            RUNTIME, (False, False), catalog(owner=RUNTIME),
            gate.EXPECTED_REVISION
        )
        self.assertTrue(any("runtime_owns_table" in item for item in errors))

    def test_schema_revision_and_missing_table_fail_closed(self):
        self.assertIn(
            "unexpected_full_schema_revision",
            gate.evaluate_catalog(RUNTIME, (False, False), catalog(), "old"),
        )
        self.assertIn(
            "missing_expected_tenant_tables",
            gate.evaluate_catalog(
                RUNTIME, (False, False), catalog()[:-1], gate.EXPECTED_REVISION
            ),
        )

    def test_valid_connection_requires_direct_neon_and_tls(self):
        self.assertEqual(
            gate.validate_runtime_url(VALID_URL, HOST, RUNTIME), VALID_URL
        )
        broken = [
            VALID_URL.replace("sslmode=require", "sslmode=disable"),
            VALID_URL.replace(HOST, "127.0.0.1"),
            VALID_URL.replace(HOST, "ep-test-pooler.aws-ap-southeast-1.neon.tech"),
            VALID_URL.replace("/neondb", "/postgres"),
            VALID_URL.replace(RUNTIME, "neondb_owner"),
            VALID_URL.replace(HOST, "elsewhere.example"),
            VALID_URL.replace("postgresql://", "http://"),
        ]
        for url in broken:
            with self.subTest(url=url[:20]):
                with self.assertRaises(ValueError):
                    gate.validate_runtime_url(url, HOST, RUNTIME)

    def test_owner_only_secret_file_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private-url"
            path.write_text(VALID_URL)
            path.chmod(0o600)
            self.assertEqual(gate.read_private_url(path), VALID_URL)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                gate.read_private_url(path)
            path.chmod(0o600)
            alias = Path(folder) / "alias"
            alias.symlink_to(path)
            with self.assertRaises(ValueError):
                gate.read_private_url(alias)

    def test_driver_failure_is_sanitized_and_nonpassing(self):
        output = StringIO()
        with patch.object(
            gate, "read_private_url",
            side_effect=ValueError("password=sensitive-credential"),
        ), redirect_stdout(output):
            status = gate.main([
                "--runtime-url-file", "/not/a/real/secret",
                "--expected-host", HOST,
                "--expected-role", RUNTIME,
            ])
        self.assertEqual(status, 1)
        self.assertIn("DB_ISOLATION_GATE=BLOCKED", output.getvalue())
        self.assertNotIn("sensitive-credential", output.getvalue())

    def test_catalog_pass_never_claims_two_user_e2e(self):
        class Result:
            def __init__(self, value):
                self.value = value
            def fetchone(self):
                return self.value
            def fetchall(self):
                return self.value

        class ReadOnlyConnection:
            def execute(self, sql):
                if "SHOW transaction_read_only" in sql:
                    return Result(("on",))
                if "current_database()" in sql:
                    return Result(("neondb", RUNTIME))
                if "rolbypassrls" in sql:
                    return Result((False, False))
                if "version_num" in sql:
                    return Result((gate.EXPECTED_REVISION,))
                return Result(catalog())
        self.assertEqual(gate.check_connection(ReadOnlyConnection(), RUNTIME), [])
        class WritableConnection(ReadOnlyConnection):
            def execute(self, sql):
                if "SHOW transaction_read_only" in sql:
                    return Result(("off",))
                return super().execute(sql)
        self.assertEqual(
            gate.check_connection(WritableConnection(), RUNTIME),
            ["connection_not_read_only"],
        )


if __name__ == "__main__":
    unittest.main()
