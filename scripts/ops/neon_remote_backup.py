#!/usr/bin/env python3
"""Read-only Neon full-release audit; optional locally retained pg_dump.

Never runs Alembic, writes SQL, changes remote database schemas, prints
connection secrets, uploads a backup or claims a restore rehearsal passed.
A backup is only a prerequisite to an independently tested recovery plan.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit


EXPECTED_PREVIOUS = "b5e4a019dc72"
EXPECTED_FULL = "d4ec2f9b7860"


def secret_file_value(path: Path) -> str:
    if path.is_symlink():
        raise ValueError("Connection file must not be a symlink")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError("Connection file must be regular and mode 600")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ValueError("Connection file must be owned by current user")
    if info.st_size > 8192:
        raise ValueError("Connection file is unexpectedly large")
    value = path.read_text(encoding="utf-8").strip()
    if value != value.strip('"').strip("'") or "\n" in value:
        raise ValueError("Connection file must contain one bare URL")
    return value


def parse_neon_url(value: str, expected_host: str) -> tuple[str, dict[str, str]]:
    if value.startswith("postgresql+psycopg://"):
        value = "postgresql://" + value[len("postgresql+psycopg://"):]
    url = urlsplit(value)
    if url.scheme != "postgresql" or not url.hostname:
        raise ValueError("Expected a PostgreSQL connection URL")
    host = url.hostname.lower()
    if not expected_host or host != expected_host.lower():
        raise ValueError("Neon host does not match explicit approved target")
    if not host.endswith(".neon.tech"):
        raise ValueError("Only an approved Neon database is allowed")
    if not url.username or not url.password or not url.path.strip("/"):
        raise ValueError("Database credentials or name missing")
    if url.fragment:
        raise ValueError("No URL fragment is permitted")
    try:
        port = url.port or 5432
    except ValueError as exc:
        raise ValueError("Invalid PostgreSQL port") from exc
    if port != 5432:
        raise ValueError("Unexpected Neon port")
    query = parse_qs(url.query, strict_parsing=True)
    # libpq accepts host, hostaddr, port, user and dbname in URL query.
    # Reject every override, including multi-valued keys, to prevent a
    # visually approved Neon hostname pointing at a different server.
    if not set(query).issubset({"sslmode", "channel_binding"}):
        raise ValueError("Unexpected connection query parameter")
    if any(len(values) != 1 for values in query.values()):
        raise ValueError("Ambiguous connection query parameters")
    if query.get("sslmode") not in (["require"], ["verify-full"]):
        raise ValueError("TLS must be enforced by sslmode=require/verify-full")
    return value, {"host": host, "port": str(port), "tls": query["sslmode"][0]}



def assert_target_identity(
    connection_url: str, conn, expected_database: str, expected_role: str,
) -> None:
    """Fail closed on the exact connected database and current SQL role.

    Host-only validation is insufficient because one Neon endpoint can
    serve more than one database and a credential may select another role.
    Only fixed pass/fail diagnostics are printed by the CLI.
    """
    if not expected_database or not expected_role:
        raise ValueError("Exact database and SQL role must be approved")
    u = urlsplit(connection_url)
    if (
        unquote(u.path.lstrip("/")) != expected_database
        or unquote(u.username or "") != expected_role
    ):
        raise ValueError("Approved URL database or role mismatch")
    record = conn.execute(
        "SELECT current_database(), current_user"
    ).fetchone()
    if (
        record is None or len(record) != 2
        or record[0] != expected_database
        or record[1] != expected_role
    ):
        raise ValueError("Connected PostgreSQL identity mismatch")



def audit_revision(conn) -> tuple[str, bool]:
    row = conn.execute(
        "SELECT to_regclass('public.alembic_version') IS NOT NULL, "
        "to_regclass('public.users') IS NOT NULL, "
        "to_regclass('public.documents') IS NOT NULL, "
        "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
    ).fetchone()
    if row is None or not all(row):
        raise ValueError("Missing migration table, core schema or pgvector")
    versions = [
        record[0] for record in
        conn.execute("SELECT version_num FROM public.alembic_version").fetchall()
    ]
    if len(versions) != 1:
        raise ValueError("Unexpected number of Alembic heads in database")
    revision = versions[0]
    if revision not in (EXPECTED_PREVIOUS, EXPECTED_FULL):
        raise ValueError("Database revision requires manual review")

    # Alembic can be stamped or drift independently of the actual schema.
    # Verify ALL four Study Abroad tables, not just the revision label.
    study_schema = conn.execute(
        "SELECT "
        "to_regclass('public.study_cases') IS NOT NULL, "
        "to_regclass('public.study_case_documents') IS NOT NULL, "
        "to_regclass('public.study_research_reports') IS NOT NULL, "
        "to_regclass('public.study_universities') IS NOT NULL"
    ).fetchone()
    if study_schema is None or len(study_schema) != 4:
        raise ValueError("Study Abroad schema inspection unavailable")
    if revision == EXPECTED_FULL and not all(study_schema):
        raise ValueError("Full migration revision but Study Abroad tables missing")
    if revision == EXPECTED_PREVIOUS and any(study_schema):
        raise ValueError("Unexpected Study Abroad tables before full migration")
    return revision, revision == EXPECTED_FULL


class BackupClientVersionError(ValueError):
    """Only vetted, non-secret PostgreSQL tool/version diagnostics."""


def _client_major(tool: str) -> int:
    """Parse the installed pg_dump/pg_restore major, never its environment."""
    location = shutil.which(tool)
    if location is None:
        raise BackupClientVersionError(f"{tool} is missing")
    try:
        output = subprocess.run(
            [location, "--version"], capture_output=True, text=True,
            check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackupClientVersionError(f"{tool} version unavailable") from exc
    if output.returncode != 0:
        raise BackupClientVersionError(f"{tool} version unavailable")
    # Version text is never echoed. Avoid terminal-control/log injection.
    match = re.fullmatch(
        rf"{re.escape(tool)} \(PostgreSQL\) (\d{{1,2}})(?:\.\d+)?(?: .*)?",
        output.stdout.strip(),
    )
    if not match:
        raise BackupClientVersionError(f"{tool} version unrecognized")
    major = int(match.group(1))
    if not 10 <= major <= 30:
        raise BackupClientVersionError(f"{tool} version unsupported")
    return major


def verify_backup_clients(server_major: int) -> None:
    """Refuse a client older than Neon, before touching backup files."""
    if not isinstance(server_major, int) or not 10 <= server_major <= 30:
        raise BackupClientVersionError("Neon server version unrecognized")
    for tool in ("pg_dump", "pg_restore"):
        major = _client_major(tool)
        if major < server_major:
            raise BackupClientVersionError(
                f"{tool} {major} is older than PostgreSQL {server_major}"
            )


def neon_server_major(conn) -> int:
    """Query live version with psycopg v3 Cursor.fetchone(), not SQLAlchemy."""
    row = conn.execute(
        "SELECT current_setting('server_version_num')"
    ).fetchone()
    if (
        row is None or len(row) != 1
        or not isinstance(row[0], str)
        or not row[0].isdigit()
    ):
        raise BackupClientVersionError("Neon server version unavailable")
    major = int(row[0]) // 10000
    if not 10 <= major <= 30:
        raise BackupClientVersionError("Neon server version unsupported")
    return major


def create_backup(
    connection_url: str, backup_dir: Path, revision: str,
    server_major: int,
) -> None:
    # Detect the exact PG16->PG18 failure seen on the owner Mac.
    # Fail before creating files or executing a backup subprocess.
    verify_backup_clients(server_major)
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if backup_dir.is_symlink() or backup_dir.stat().st_mode & 0o077:
        raise ValueError("Backup directory must be private (mode 700)")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"aqlyra-neon-{timestamp}-{os.getpid()}"
    partial = backup_dir / f".{name}.partial"
    final = backup_dir / f"{name}.dump"
    manifest = backup_dir / f"{name}.json"
    if partial.exists() or final.exists() or manifest.exists():
        raise ValueError("Backup filename collision")
    # Never place the DSN in command-line arguments or emitted logs.
    # Ignore inherited libpq parameters (especially PGHOSTADDR/PGSERVICE)
    # that could redirect the local dump away from the checked Neon host.
    env = {
        key: val for key, val in os.environ.items()
        if not key.startswith("PG")
    }
    env["PGCONNECT_TIMEOUT"] = "10"
    args = [
        "pg_dump", "--format=custom", "--no-owner", "--no-acl",
        "--file", str(partial),
    ]
    # libpq reads PGPASSWORD and other connection fields from PG* env.
    from urllib.parse import unquote
    u = urlsplit(connection_url)
    env.update({
        "PGHOST": u.hostname or "",
        "PGPORT": str(u.port or 5432),
        "PGUSER": unquote(u.username or ""),
        "PGPASSWORD": unquote(u.password or ""),
        "PGDATABASE": unquote(u.path.lstrip("/")),
        "PGSSLMODE": parse_qs(u.query)["sslmode"][0],
        "PGCHANNELBINDING": parse_qs(u.query).get(
            "channel_binding", ["prefer"]
        )[0],
    })
    os.umask(0o077)
    try:
        result = subprocess.run(
            args, env=env, capture_output=True, timeout=240, check=False
        )
        if result.returncode != 0:
            raise RuntimeError("pg_dump failed; inspect locally without sharing secrets")
        check = subprocess.run(
            ["pg_restore", "--list", str(partial)],
            capture_output=True, timeout=45, check=False
        )
        if check.returncode != 0 or not check.stdout:
            raise RuntimeError("Archive structure verification failed")
        digest = hashlib.sha256(partial.read_bytes()).hexdigest()
        partial.replace(final)
        # Contains only the archive filename/checksum and schema revision.
        with manifest.open("x", encoding="utf-8") as fh:
            json.dump({
                "format": "aqlyra-neon-backup.v1",
                "archive": final.name,
                "sha256": digest,
                "alembic_revision": revision,
                "restore_rehearsal": "NOT_RUN",
            }, fh, indent=2)
        print("BACKUP_ARCHIVE=CREATED_PRIVATE")
        print("BACKUP_STRUCTURAL_CHECK=PASS")
        print("RESTORE_REHEARSAL=NOT_RUN")
        print(f"BACKUP_DIRECTORY={backup_dir}")
    finally:
        if partial.exists():
            partial.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-role", required=True)
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        url = secret_file_value(args.url_file)
        pg_url, details = parse_neon_url(url, args.expected_host)
        # Reject wrong database/role before even opening a network connection.
        approved_url = urlsplit(pg_url)
        if (
            unquote(approved_url.path.lstrip("/")) != args.expected_database
            or unquote(approved_url.username or "") != args.expected_role
        ):
            raise ValueError("Connection URL does not identify approved DB and role")
        # Backup/migrations require an unpooled direct Neon connection.
        # The -pooler URL is appropriate for live API traffic only.
        if (
            args.backup_dir is not None
            and details["host"].split(".", 1)[0].endswith("-pooler")
        ):
            raise ValueError("Use the direct (unpooled) Neon URL for pg_dump")
        try:
            import psycopg
        except ImportError as exc:
            raise ValueError("psycopg v3 is required; use backend virtualenv") from exc
        # libpq environment defaults such as PGHOSTADDR must not
        # override the explicitly approved Neon URL even for audit.
        inherited_pg = {
            key: value for key, value in os.environ.items()
            if key.startswith("PG")
        }
        try:
            for key in inherited_pg:
                os.environ.pop(key, None)
            with psycopg.connect(
                pg_url, connect_timeout=10,
                options="-c default_transaction_read_only=on",
            ) as conn:
                assert_target_identity(
                    pg_url, conn, args.expected_database, args.expected_role,
                )
                revision, is_full = audit_revision(conn)
                # Psycopg 3 cursors implement fetchone(), not scalar_one().
                server_major = neon_server_major(conn)
                conn.rollback()
        finally:
            os.environ.update(inherited_pg)
        print("NEON_TARGET_AND_TLS=PASS")
        print("NEON_SCHEMA=PASS")
        print(f"ALEMBIC_REVISION={revision}")
        print("FULL_RELEASE_SCHEMA=" + ("READY" if is_full else "MIGRATION_PENDING"))
        if args.backup_dir is not None:
            create_backup(pg_url, args.backup_dir, revision, server_major)
        return 0
    except BackupClientVersionError as exc:
        # Generated from validated tool names and numeric major versions only.
        # Never include provider stderr, DSNs, credentials or object names.
        print(f"NEON_BACKUP_CLIENT=BLOCKED ({exc})", file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        # Diagnostics are deliberately generic; DB exceptions may hold DSNs.
        print(f"NEON_PREFLIGHT=BLOCKED ({type(exc).__name__})", file=sys.stderr)
        return 2
    except Exception:
        print("NEON_PREFLIGHT=BLOCKED (connection or query failure)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
