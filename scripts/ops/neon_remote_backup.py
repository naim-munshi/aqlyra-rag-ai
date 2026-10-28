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
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit


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
    return revision, revision == EXPECTED_FULL


def create_backup(
    connection_url: str, backup_dir: Path, revision: str
) -> None:
    if not shutil.which("pg_dump") or not shutil.which("pg_restore"):
        raise ValueError("PostgreSQL pg_dump and pg_restore required")
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
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        url = secret_file_value(args.url_file)
        pg_url, _ = parse_neon_url(url, args.expected_host)
        try:
            import psycopg
        except ImportError as exc:
            raise ValueError("psycopg v3 is required; use backend virtualenv") from exc
        with psycopg.connect(
            pg_url, connect_timeout=10, options="-c default_transaction_read_only=on"
        ) as conn:
            revision, is_full = audit_revision(conn)
            conn.rollback()
        print("NEON_TARGET_AND_TLS=PASS")
        print("NEON_SCHEMA=PASS")
        print(f"ALEMBIC_REVISION={revision}")
        print("FULL_RELEASE_SCHEMA=" + ("READY" if is_full else "MIGRATION_PENDING"))
        if args.backup_dir is not None:
            create_backup(pg_url, args.backup_dir, revision)
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        # Diagnostics are deliberately generic; DB exceptions may hold DSNs.
        print(f"NEON_PREFLIGHT=BLOCKED ({type(exc).__name__})", file=sys.stderr)
        return 2
    except Exception:
        print("NEON_PREFLIGHT=BLOCKED (connection or query failure)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
