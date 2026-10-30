#!/usr/bin/env python3
"""Read-only prerequisite check for Aqlyra's public-launch database isolation.

This checks catalog configuration, NOT authorization correctness. A successful
result must still be followed by a separate two-tenant negative-access E2E
test on restored staging. Never run migrations or change production RLS here.
"""
import argparse
import os
from pathlib import Path
import stat
from urllib.parse import parse_qs, unquote, urlsplit

EXPECTED_REVISION = "d4ec2f9b7860"
TENANT_TABLES = frozenset((
    "cloud_upload_intents", "conversation_documents", "conversations",
    "document_chunks", "document_units", "documents",
    "email_verification_codes", "embedding_records", "memories",
    "memory_embeddings", "message_attachments", "messages",
    "password_reset_codes", "projects", "study_case_documents",
    "study_cases", "study_research_reports", "study_universities", "users",
))


def validate_runtime_url(raw: str, expected_host: str, expected_role: str) -> str:
    """Validate private runtime connection identity before any network call."""
    url = raw.strip()
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        user = unquote(parsed.username or "")
        _ = parsed.port
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid private database URL") from exc
    if parsed.scheme not in ("postgres", "postgresql", "postgresql+psycopg"):
        raise ValueError("PostgreSQL URL scheme required")
    if not expected_host or host != expected_host.lower():
        raise ValueError("Database host identity mismatch")
    if not host.endswith(".neon.tech") or "-pooler." in host:
        raise ValueError("Direct Neon hostname required")
    if parsed.path != "/neondb" or parsed.fragment:
        raise ValueError("Unexpected database name or URL fragment")
    if user != expected_role or not expected_role or user == "neondb_owner":
        raise ValueError("Restricted runtime role required, not database owner")
    if parsed.password is None:
        raise ValueError("Private runtime credentials missing")
    ssl_modes = parse_qs(parsed.query).get("sslmode", [])
    if ssl_modes != ["require"] and ssl_modes != ["verify-full"]:
        raise ValueError("Explicit TLS sslmode=require or verify-full required")
    if parsed.scheme == "postgresql+psycopg":
        return "postgresql://" + url.split("://", 1)[1]
    return url


def read_private_url(path: Path) -> str:
    """Refuse public/group-readable files and symlink redirection."""
    file_stat = path.lstat()
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != os.getuid()
        or stat.S_IMODE(file_stat.st_mode) & 0o077
    ):
        raise ValueError("Private URL file must be owner-only regular file (0600)")
    value = path.read_text(encoding="utf-8").strip()
    if not value or "\n" in value:
        raise ValueError("One private database URL per file required")
    return value


def evaluate_catalog(runtime_role: str, role_flags, rows, revision: str):
    """Return only non-secret fail-closed observations about RLS coverage."""
    failures = []
    if revision != EXPECTED_REVISION:
        failures.append("unexpected_full_schema_revision")
    if role_flags is None or bool(role_flags[0]) or bool(role_flags[1]):
        failures.append("runtime_role_bypasses_rls")
    catalog = {name: (bool(rls), owner, int(policy_count))
               for name, rls, owner, policy_count in rows}
    missing = sorted(TENANT_TABLES - catalog.keys())
    if missing:
        failures.append("missing_expected_tenant_tables")
    for table_name in sorted(TENANT_TABLES & catalog.keys()):
        rls_enabled, owner, policy_count = catalog[table_name]
        if owner == runtime_role:
            failures.append(f"{table_name}:runtime_owns_table")
        if not rls_enabled:
            failures.append(f"{table_name}:rls_disabled")
        if policy_count < 1:
            failures.append(f"{table_name}:no_policy")
    return failures


def check_connection(conn, expected_role: str):
    if conn.execute("SHOW transaction_read_only").fetchone()[0] != "on":
        return ["connection_not_read_only"]
    db_name, role = conn.execute(
        "SELECT current_database(), current_user"
    ).fetchone()
    if db_name != "neondb" or role != expected_role:
        return ["database_or_role_identity_mismatch"]
    role_flags = conn.execute(
        "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    revision_row = conn.execute(
        "SELECT version_num FROM public.alembic_version LIMIT 1"
    ).fetchone()
    revision = revision_row[0] if revision_row else ""
    rows = conn.execute("""
        SELECT c.relname, c.relrowsecurity, pg_get_userbyid(c.relowner),
               (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    """).fetchall()
    return evaluate_catalog(role, role_flags, rows, revision)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-url-file", type=Path, required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-role", required=True)
    args = parser.parse_args(argv)
    try:
        url = validate_runtime_url(
            read_private_url(args.runtime_url_file),
            args.expected_host,
            args.expected_role,
        )
        # Imported only on real execution, never needed for pure unit tests.
        import psycopg
        with psycopg.connect(
            url, connect_timeout=5,
            options="-c default_transaction_read_only=on",
        ) as conn:
            failures = check_connection(conn, args.expected_role)
            conn.rollback()
    except Exception:
        # Never emit driver errors, connection strings, tokens, or server SQL.
        print("DB_ISOLATION_GATE=BLOCKED reason=private_connection_or_audit")
        return 1
    if failures:
        for failure in failures:
            print("BLOCKED " + failure)
        print("DB_ISOLATION_GATE=BLOCKED")
        return 1
    print(f"DB_RLS_CATALOG=PASS tables={len(TENANT_TABLES)}")
    print("DB_ISOLATION_GATE=PRELIMINARY_PASS")
    print("TWO_TENANT_E2E=STILL_REQUIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
