"""Self-contained, offline tests for Neon remote backup preflight contracts."""
import importlib.util
from pathlib import Path
import os
import stat
import tempfile
import unittest
from unittest.mock import Mock

MODULE = Path(__file__).with_name("neon_remote_backup.py")
spec = importlib.util.spec_from_file_location("neon_remote_backup", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HOST = "ep-private-pooler.ap-southeast-1.aws.neon.tech"
URL = f"postgresql://neondb_owner:percent%40encoded@{HOST}/neondb?sslmode=require&channel_binding=require"


class NeonRemoteBackupSafetyTest(unittest.TestCase):
    def test_neon_tls_host_and_ssl_requirements(self):
        url, details = gate.parse_neon_url(URL, HOST)
        self.assertEqual(url, URL)
        self.assertEqual(details["host"], HOST)
        self.assertEqual(details["tls"], "require")

    def test_sqlalchemy_psycopg_v3_selector_normalized(self):
        raw = URL.replace("postgresql://", "postgresql+psycopg://", 1)
        actual, _ = gate.parse_neon_url(raw, HOST)
        self.assertEqual(actual, URL)

    def test_host_mismatch_is_denied(self):
        with self.assertRaises(ValueError):
            gate.parse_neon_url(URL, "ep-other-pooler.aws.neon.tech")

    def test_non_neon_hostname_is_denied(self):
        bad = URL.replace(HOST, "db.example.com")
        with self.assertRaises(ValueError):
            gate.parse_neon_url(bad, "db.example.com")

    def test_unencrypted_or_rest_api_urls_are_denied(self):
        for bad in [
            URL.replace("sslmode=require", "sslmode=disable"),
            URL.replace("postgresql://", "https://", 1),
            URL + "#secret",
            URL.replace("/neondb?", "/?"),
            URL.replace("sslmode=require", "sslmode=prefer"),
            URL + "&host=evil.example.invalid",
            URL + "&hostaddr=127.0.0.1",
            URL + "&port=5433",
            URL + "&dbname=other_db",
            URL + "&service=unapproved",
            URL + "&sslmode=disable",
        ]:
            with self.subTest(url_kind=bad[:9]):
                with self.assertRaises(ValueError):
                    gate.parse_neon_url(bad, HOST)

    def test_private_file_permissions_and_raw_value(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "db.url"
            p.write_text(URL, encoding="utf-8")
            p.chmod(0o600)
            self.assertEqual(gate.secret_file_value(p), URL)
            p.chmod(0o644)
            with self.assertRaises(ValueError):
                gate.secret_file_value(p)
            p.chmod(0o600)
            p.write_text(URL + '\nREDIS_URL=not-allowed', encoding="utf-8")
            with self.assertRaises(ValueError):
                gate.secret_file_value(p)
            p.write_text(URL, encoding="utf-8")
            link = Path(root) / "linked.url"
            link.symlink_to(p)
            with self.assertRaises(ValueError):
                gate.secret_file_value(link)

    def test_pooled_endpoint_cannot_be_used_for_backup(self):
        with tempfile.TemporaryDirectory() as root:
            url_file = Path(root) / "neon.url"
            url_file.write_text(URL, encoding="utf-8")
            url_file.chmod(0o600)
            status = gate.main([
                "--url-file", str(url_file),
                "--expected-host", HOST,
                "--expected-database", "neondb",
                "--expected-role", "neondb_owner",
                "--backup-dir", str(Path(root) / "backup"),
            ])
            self.assertEqual(status, 2)
            self.assertFalse((Path(root) / "backup").exists())

    def test_schema_preflight_requires_vector_core_tables_single_revision(self):
        def fake_conn(row, versions, study=(False,) * 4):
            conn = Mock()
            conn.execute.side_effect = [
                Mock(fetchone=lambda: row),
                Mock(fetchall=lambda: [(x,) for x in versions]),
                Mock(fetchone=lambda: study),
            ]
            return conn

        self.assertEqual(
            gate.audit_revision(fake_conn((True,) * 4, [gate.EXPECTED_PREVIOUS])),
            (gate.EXPECTED_PREVIOUS, False),
        )
        self.assertEqual(
            gate.audit_revision(
                fake_conn((True,) * 4, [gate.EXPECTED_FULL], (True,) * 4)
            ),
            (gate.EXPECTED_FULL, True),
        )
        for row, versions, study in [
            ((False, True, True, True), [gate.EXPECTED_FULL], (True,) * 4),
            ((True,) * 4, [], (False,) * 4),
            ((True,) * 4, ["unknown"], (False,) * 4),
            ((True,) * 4, [gate.EXPECTED_PREVIOUS, gate.EXPECTED_FULL], (False,) * 4),
            ((True,) * 4, [gate.EXPECTED_FULL], (False,) * 4),
            ((True,) * 4, [gate.EXPECTED_FULL], (True, True, False, True)),
            ((True,) * 4, [gate.EXPECTED_PREVIOUS], (True, False, False, False)),
            ((True,) * 4, [gate.EXPECTED_PREVIOUS], None),
        ]:
            with self.subTest(row=row, versions=versions, study=study):
                with self.assertRaises(ValueError):
                    gate.audit_revision(fake_conn(row, versions, study))


    def test_exact_database_and_role_identity_fails_closed(self):
        from unittest.mock import Mock
        correct = Mock()
        correct.execute.return_value.fetchone.return_value = (
            "neondb", "neondb_owner",
        )
        gate.assert_target_identity(URL, correct, "neondb", "neondb_owner")
        correct.execute.assert_called_once_with(
            "SELECT current_database(), current_user"
        )
        for expected_db, expected_role in [
            ("wrong_db", "neondb_owner"),
            ("neondb", "other_role"),
        ]:
            with self.subTest(expected_db=expected_db, expected_role=expected_role):
                with self.assertRaises(ValueError):
                    gate.assert_target_identity(URL, Mock(), expected_db, expected_role)

        bad_conn = Mock()
        for observed in [
            ("other_db", "neondb_owner"),
            ("neondb", "other_role"),
            None,
            ("neondb",),
        ]:
            bad_conn.execute.return_value.fetchone.return_value = observed
            with self.subTest(observed=observed):
                with self.assertRaises(ValueError):
                    gate.assert_target_identity(
                        URL, bad_conn, "neondb", "neondb_owner",
                    )

    def test_wrong_url_target_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            url_file = Path(root) / "url"
            url_file.write_text(URL)
            url_file.chmod(0o600)
            for database, role in [
                ("other_db", "neondb_owner"),
                ("neondb", "other_role"),
            ]:
                with self.subTest(database=database, role=role):
                    status = gate.main([
                        "--url-file", str(url_file), "--expected-host", HOST,
                        "--expected-database", database, "--expected-role", role,
                    ])
                    self.assertEqual(status, 2)



    def test_restore_rehearsal_shell_safety_contract(self):
        import subprocess
        script = Path(__file__).with_name("neon_restore_rehearsal.sh")
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        content = script.read_text(encoding="utf-8")
        self.assertIn("--network none", content)
        self.assertIn("--exit-on-error", content)
        self.assertIn("to_regclass('public.study_cases')", content)
        self.assertIn("to_regclass('public.study_case_documents')", content)
        self.assertIn("to_regclass('public.study_research_reports')", content)
        self.assertIn("to_regclass('public.study_universities')", content)
        self.assertIn("RESTORE_REHEARSAL=BLOCKED study schema incomplete", content)
        self.assertIn("RESTORE_REHEARSAL=BLOCKED unexpected study schema drift", content)



    def test_postgres_clients_require_server_compatible_major(self):
        from unittest.mock import patch
        # PostgreSQL 16 pg_dump/restore must not touch a Neon PG18 backup.
        with patch.object(gate, "_client_major", side_effect=[16]):
            with self.assertRaisesRegex(
                gate.BackupClientVersionError, "pg_dump 16 is older"
            ):
                gate.verify_backup_clients(18)
        with patch.object(gate, "_client_major", side_effect=[18, 16]):
            with self.assertRaisesRegex(
                gate.BackupClientVersionError, "pg_restore 16 is older"
            ):
                gate.verify_backup_clients(18)
        with patch.object(gate, "_client_major", side_effect=[18, 18]):
            gate.verify_backup_clients(18)

        # Safety: invalid/untrusted server major cannot bypass checks.
        for bad in [0, -1, 1000, "18", None, True]:
            with self.subTest(bad=bad):
                with self.assertRaises(gate.BackupClientVersionError):
                    gate.verify_backup_clients(bad)

    def test_pg_client_version_parser_is_strict_and_redacted(self):
        from unittest.mock import patch
        responses = [
            ("pg_dump", "pg_dump (PostgreSQL) 16.14 (Homebrew)", 16),
            ("pg_dump", "pg_dump (PostgreSQL) 18.6", 18),
            ("pg_restore", "pg_restore (PostgreSQL) 18.6 (Homebrew)", 18),
        ]
        for tool, stdout, major in responses:
            with self.subTest(tool=tool, stdout=stdout):
                with patch.object(gate.shutil, "which", return_value="/fake/client"), \
                     patch.object(
                        gate.subprocess, "run",
                        return_value=Mock(returncode=0, stdout=stdout),
                     ):
                    self.assertEqual(gate._client_major(tool), major)
        with patch.object(gate.shutil, "which", return_value="/fake/client"), \
             patch.object(gate.subprocess, "run", return_value=Mock(
                 returncode=0, stdout="pg_dump (PostgreSQL) 18\nPRIVATE=SECRET",
             )):
            with self.assertRaises(gate.BackupClientVersionError):
                gate._client_major("pg_dump")

    def test_incompatible_client_refuses_before_backup_dir_creation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "never-create"
            with patch.object(
                gate, "verify_backup_clients",
                side_effect=gate.BackupClientVersionError(
                    "pg_dump 16 is older than PostgreSQL 18"
                ),
            ):
                with self.assertRaises(gate.BackupClientVersionError):
                    gate.create_backup(
                        "postgresql://neondb_owner:secret@host/neondb",
                        directory, gate.EXPECTED_PREVIOUS, 18,
                    )
            self.assertFalse(directory.exists())


    def test_operator_recovery_gate_syntax_and_fail_closed(self):
        import subprocess
        script = Path(__file__).with_name("neon_full_release_recovery_gate.sh")
        check = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(check.returncode, 0)
        missing = subprocess.run(
            ["bash", str(script)],
            capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(missing.returncode, 2)
        content = script.read_text(encoding="utf-8")
        self.assertIn("--expected-database", content)
        self.assertIn("--expected-role", content)
        self.assertIn("--expected-host", content)
        self.assertIn("neon_remote_backup.py", content)
        self.assertIn("neon_restore_rehearsal.sh", content)
        self.assertIn("ALEMBIC_REVISION=b5e4a019dc72", content)
        self.assertIn("FULL_RELEASE_DATABASE_MIGRATION=NOT_RUN", content)
        self.assertIn("NEON_PRIVATE_BACKUP=PASS", content)
        self.assertNotIn("alembic upgrade head\n", content)



if __name__ == "__main__":
    unittest.main()
