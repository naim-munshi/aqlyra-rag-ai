#!/usr/bin/env python3
"""Read-only, owner-scoped Neon Core/Full Study Abroad schema audit.

Never upgrades, creates or alters tables; does not open any backup archive.
Run only with a 0600 direct Neon URL and explicit phase/target identity.
Checks full schema ownership FKs and indexes, not just Alembic stamping.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

_BACKUP = Path(__file__).with_name("neon_remote_backup.py")
_spec = importlib.util.spec_from_file_location("neon_remote_backup_audit", _BACKUP)
backup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup)

CORE_TABLES = frozenset({
    "alembic_version", "cloud_upload_intents",
    "conversation_documents", "conversations", "document_chunks",
    "document_units", "documents", "email_verification_codes",
    "embedding_records", "memories", "memory_embeddings",
    "message_attachments", "messages", "password_reset_codes",
    "projects", "users",
})
STUDY_TABLES = frozenset({
    "study_cases", "study_case_documents",
    "study_research_reports", "study_universities",
})
STUDY_FOREIGN_KEYS = frozenset({
    ("study_cases", "users", "c"),
    ("study_case_documents", "study_cases", "c"),
    ("study_case_documents", "documents", "c"),
    ("study_research_reports", "study_cases", "c"),
    ("study_universities", "study_cases", "c"),
})
STUDY_INDEXES = frozenset({
    "ix_study_cases_owner_updated",
    "ix_study_research_reports_case_id",
    "ix_study_universities_case_id",
})


class StudySchemaBlocked(ValueError):
    """All messages avoid SQL/provider errors, object contents, and secrets."""


def audit_schema(conn, phase: str) -> tuple[str, int]:
    """Use only constant catalog reads, never user-composed SQL strings."""
    if phase not in ("core", "full"):
        raise StudySchemaBlocked("invalid expected schema phase")
    observed = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchall()
    tables = {row[0] for row in observed}
    expected = CORE_TABLES | (STUDY_TABLES if phase == "full" else frozenset())
    if len(tables) != len(observed) or tables != expected:
        raise StudySchemaBlocked("unexpected Core/Full table inventory")
    if phase == "full":
        refs = conn.execute(
            "SELECT child.relname, parent.relname, fk.confdeltype "
            "FROM pg_constraint fk "
            "JOIN pg_class child ON child.oid=fk.conrelid "
            "JOIN pg_class parent ON parent.oid=fk.confrelid "
            "JOIN pg_namespace n ON n.oid=child.relnamespace "
            "WHERE n.nspname='public' AND fk.contype='f' "
            "AND child.relname IN ("
            "'study_cases','study_case_documents',"
            "'study_research_reports','study_universities')"
        ).fetchall()
        if set(refs) != STUDY_FOREIGN_KEYS or len(refs) != len(STUDY_FOREIGN_KEYS):
            raise StudySchemaBlocked("Study Abroad owner FK/cascade drift")
        indexes = conn.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname='public' AND tablename IN ("
            "'study_cases','study_case_documents',"
            "'study_research_reports','study_universities') "
            "AND indexname LIKE 'ix_study_%'"
        ).fetchall()
        names = {row[0] for row in indexes}
        if names != STUDY_INDEXES or len(indexes) != len(STUDY_INDEXES):
            raise StudySchemaBlocked("Study Abroad index drift")
    return phase, len(tables)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-role", required=True)
    parser.add_argument(
        "--expected-phase", required=True, choices=("core", "full"),
    )
    args = parser.parse_args(argv)
    try:
        if args.expected_database != "neondb" or args.expected_role != "neondb_owner":
            raise StudySchemaBlocked("unexpected database/role")
        pg_url, _ = backup.parse_neon_url(
            backup.secret_file_value(args.url_file), args.expected_host
        )
        import psycopg

        with psycopg.connect(
            pg_url, connect_timeout=10,
            options="-c default_transaction_read_only=on",
        ) as conn:
            backup.assert_target_identity(
                pg_url, conn, args.expected_database, args.expected_role
            )
            read_only = conn.execute("SHOW transaction_read_only").fetchone()
            if read_only != ("on",):
                raise StudySchemaBlocked("connection not read-only")
            revision, is_full = backup.audit_revision(conn)
            phase = "full" if is_full else "core"
            if phase != args.expected_phase:
                raise StudySchemaBlocked("Alembic phase does not match expected")
            schema, count = audit_schema(conn, args.expected_phase)
            conn.rollback()
    except (OSError, ValueError, RuntimeError, TypeError, AttributeError):
        print("STUDY_SCHEMA_AUDIT=BLOCKED", file=sys.stderr)
        return 2
    except Exception:
        # Do not leak arbitrary driver exception text, SQL or connection URL.
        print("STUDY_SCHEMA_AUDIT=BLOCKED", file=sys.stderr)
        return 2

    print("NEON_TARGET_TLS_AND_READONLY=PASS")
    print("NEON_SCHEMA_TABLES=PASS")
    print("NEON_STUDY_FK_INDEX=PASS" if schema == "full"
          else "NEON_STUDY_FK_INDEX=NOT_APPLICABLE")
    print(f"NEON_TABLE_COUNT={count}")
    print(f"ALEMBIC_REVISION={revision}")
    print(f"EXPECTED_PHASE={schema.upper()}")
    print("DATABASE_MIGRATION=NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
