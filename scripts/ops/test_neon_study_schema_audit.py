"""Offline, secret-free tests for exact Core/Full Neon catalog assertions."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest

FILE = Path(__file__).with_name("neon_study_schema_audit.py")
spec = importlib.util.spec_from_file_location("neon_study_schema_audit", FILE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConn:
    def __init__(self, *, phase="core", tables=None, refs=None, indexes=None,
                 primary_keys=None, owner_columns=None, read_only=True):
        self.phase = phase
        self.tables = (
            tables if tables is not None
            else audit.CORE_TABLES | (
                audit.STUDY_TABLES if phase == "full" else frozenset()
            )
        )
        self.refs = refs if refs is not None else audit.STUDY_FOREIGN_KEYS
        self.indexes = indexes if indexes is not None else audit.STUDY_INDEXES
        self.primary_keys = (
            primary_keys if primary_keys is not None else audit.STUDY_PRIMARY_KEYS
        )
        self.owner_columns = (
            owner_columns if owner_columns is not None else audit.STUDY_OWNER_COLUMNS
        )
        self.read_only = read_only
        self.rolled_back = False
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)
        if sql == "SHOW transaction_read_only":
            return FakeCursor([("on" if self.read_only else "off",)])
        if "information_schema.tables" in sql:
            return FakeCursor([(name,) for name in sorted(self.tables)])
        if "FROM pg_constraint" in sql:
            return FakeCursor(sorted(self.refs))
        if "FROM pg_index" in sql:
            return FakeCursor(sorted(self.indexes))
        if "FROM pg_constraint pk" in sql:
            return FakeCursor(sorted(self.primary_keys))
        if "information_schema.columns" in sql:
            return FakeCursor(sorted(self.owner_columns))
        raise AssertionError("Only approved read-only queries are permitted")

    def rollback(self):
        self.rolled_back = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class StudySchemaAuditTest(unittest.TestCase):
    def test_real_core_inventory_contract(self):
        conn = FakeConn()
        self.assertEqual(audit.audit_schema(conn, "core"), ("core", 16))
        self.assertEqual(len(conn.executed), 1)
        self.assertTrue(all("SELECT" in query for query in conn.executed))

    def test_full_inventory_ownership_cascade_and_indexes(self):
        conn = FakeConn(phase="full")
        self.assertEqual(audit.audit_schema(conn, "full"), ("full", 20))
        self.assertEqual(len(conn.executed), 5)
        self.assertEqual(len(audit.STUDY_FOREIGN_KEYS), 5)
        self.assertEqual(len(audit.STUDY_PRIMARY_KEYS), 4)
        self.assertEqual(len(audit.STUDY_OWNER_COLUMNS), 8)

    def test_wrong_target_or_partial_schema_fails_closed(self):
        scenarios = [
            FakeConn(tables=audit.CORE_TABLES - {"users"}),
            FakeConn(tables=audit.CORE_TABLES | {"rogue_table"}),
            FakeConn(phase="full", tables=audit.CORE_TABLES),
            FakeConn(phase="full", refs=audit.STUDY_FOREIGN_KEYS - {
                ("study_cases", "users", "user_id", "id", "c")
            }),
            FakeConn(phase="full", refs=(
                audit.STUDY_FOREIGN_KEYS - {
                    ("study_cases", "users", "user_id", "id", "c")
                }
            ) | {("study_cases", "users", "id", "id", "c")}),
            FakeConn(phase="full", refs=(
                audit.STUDY_FOREIGN_KEYS - {
                    ("study_cases", "users", "user_id", "id", "c")
                }
            ) | {("study_cases", "users", "user_id", "id", "a")}),
            FakeConn(phase="full", indexes=audit.STUDY_INDEXES - {
                ("ix_study_cases_owner_updated", "study_cases", "btree",
                 False, False, False, "user_id,updated_at")
            }),
            FakeConn(phase="full", indexes=(
                audit.STUDY_INDEXES - {
                    ("ix_study_cases_owner_updated", "study_cases", "btree",
                     False, False, False, "user_id,updated_at")
                }
            ) | {("ix_study_cases_owner_updated", "study_cases", "btree",
                  False, False, False, "updated_at,user_id")}),
            FakeConn(phase="full", primary_keys=(
                audit.STUDY_PRIMARY_KEYS - {
                    ("study_case_documents", "case_id,document_id")
                }
            ) | {("study_case_documents", "document_id")}),
            FakeConn(phase="full", owner_columns=(
                audit.STUDY_OWNER_COLUMNS - {
                    ("study_cases", "user_id", "NO")
                }
            ) | {("study_cases", "user_id", "YES")}),
        ]
        for item in scenarios:
            with self.subTest(index=scenarios.index(item)):
                with self.assertRaises(audit.StudySchemaBlocked):
                    audit.audit_schema(item, item.phase)
        with self.assertRaises(audit.StudySchemaBlocked):
            audit.audit_schema(FakeConn(), "unknown")

    def run_main(self, *, phase="core", read_only=True, rev_full=None):
        connection = FakeConn(phase=phase, read_only=read_only)
        provider = SimpleNamespace(connect=lambda *a, **k: connection)
        args = [
            "--url-file", "/home/owner/private-neon-url",
            "--expected-host", "ep-test.ap-southeast-1.aws.neon.tech",
            "--expected-database", "neondb",
            "--expected-role", "neondb_owner",
            "--expected-phase", phase,
        ]
        full = phase == "full" if rev_full is None else rev_full
        out, err = StringIO(), StringIO()
        with patch.dict(sys.modules, {"psycopg": provider}), \
             patch.object(audit.backup, "secret_file_value",
                          return_value="postgresql://private-secret"), \
             patch.object(audit.backup, "parse_neon_url",
                          return_value=("postgresql://private-secret", {})), \
             patch.object(audit.backup, "assert_target_identity"), \
             patch.object(audit.backup, "audit_revision",
                          return_value=(
                              audit.backup.EXPECTED_FULL if full
                              else audit.backup.EXPECTED_PREVIOUS, full
                          )), \
             redirect_stdout(out), redirect_stderr(err):
            code = audit.main(args)
        return code, out.getvalue(), err.getvalue(), connection

    def test_core_and_full_main_are_readonly_and_never_leak_password(self):
        for phase, count in (("core", 16), ("full", 20)):
            with self.subTest(phase=phase):
                code, out, err, conn = self.run_main(phase=phase)
                self.assertEqual(code, 0)
                self.assertIn(f"NEON_TABLE_COUNT={count}", out)
                self.assertIn("DATABASE_MIGRATION=NOT_RUN", out)
                self.assertIn("NEON_TARGET_TLS_AND_READONLY=PASS", out)
                self.assertTrue(conn.rolled_back)
                self.assertNotIn("private-secret", out + err)

    def test_wrong_phase_or_missing_readonly_transaction_blocks_without_leak(self):
        for args in ({"phase": "core", "rev_full": True},
                     {"phase": "full", "rev_full": False},
                     {"phase": "core", "read_only": False}):
            code, out, err, _ = self.run_main(**args)
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertEqual(err, "STUDY_SCHEMA_AUDIT=BLOCKED\n")

    def test_failing_driver_never_echoes_provider_secrets(self):
        with patch.object(audit.backup, "secret_file_value",
                          side_effect=RuntimeError("private password leaked?")), \
             redirect_stdout(StringIO()) as out, \
             redirect_stderr(StringIO()) as err:
            code = audit.main([
                "--url-file", "/not-real", "--expected-host", "invalid",
                "--expected-database", "neondb",
                "--expected-role", "neondb_owner", "--expected-phase", "core",
            ])
        self.assertEqual(code, 2)
        self.assertNotIn("password", out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()
