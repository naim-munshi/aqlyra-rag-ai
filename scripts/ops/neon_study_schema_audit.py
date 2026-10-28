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
    ("study_cases", "users", "user_id", "id", "c"),
    ("study_case_documents", "study_cases", "case_id", "id", "c"),
    ("study_case_documents", "documents", "document_id", "id", "c"),
    ("study_research_reports", "study_cases", "case_id", "id", "c"),
    ("study_universities", "study_cases", "case_id", "id", "c"),
})
# Name, owning table, method, unique, partial, expression, key columns.
STUDY_INDEXES = frozenset({
    ("ix_study_cases_owner_updated", "study_cases", "btree",
     False, False, False, "user_id,updated_at"),
    ("ix_study_research_reports_case_id", "study_research_reports", "btree",
     False, False, False, "case_id"),
    ("ix_study_universities_case_id", "study_universities", "btree",
     False, False, False, "case_id"),
})
STUDY_PRIMARY_KEYS = frozenset({
    ("study_cases", "id"),
    ("study_case_documents", "case_id,document_id"),
    ("study_research_reports", "id"),
    ("study_universities", "id"),
})
STUDY_OWNER_COLUMNS = frozenset({
    ("study_cases", "id", "NO"),
    ("study_cases", "user_id", "NO"),
    ("study_case_documents", "case_id", "NO"),
    ("study_case_documents", "document_id", "NO"),
    ("study_research_reports", "id", "NO"),
    ("study_research_reports", "case_id", "NO"),
    ("study_universities", "id", "NO"),
    ("study_universities", "case_id", "NO"),
})
STUDY_NAMES_SQL = (
    "'study_cases','study_case_documents',"
    "'study_research_reports','study_universities'"
)


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
            "SELECT child.relname, parent.relname, "
            "array_to_string(ARRAY(SELECT att.attname FROM "
            "unnest(fk.conkey) WITH ORDINALITY AS k(attnum, ord) "
            "JOIN pg_attribute att ON att.attrelid=child.oid "
            "AND att.attnum=k.attnum ORDER BY k.ord), ','), "
            "array_to_string(ARRAY(SELECT att.attname FROM "
            "unnest(fk.confkey) WITH ORDINALITY AS k(attnum, ord) "
            "JOIN pg_attribute att ON att.attrelid=parent.oid "
            "AND att.attnum=k.attnum ORDER BY k.ord), ','), "
            "fk.confdeltype "
            "FROM pg_constraint fk "
            "JOIN pg_class child ON child.oid=fk.conrelid "
            "JOIN pg_class parent ON parent.oid=fk.confrelid "
            "JOIN pg_namespace n ON n.oid=child.relnamespace "
            "WHERE n.nspname='public' AND fk.contype='f' "
            "AND child.relname IN (" + STUDY_NAMES_SQL + ")"
        ).fetchall()
        if set(refs) != STUDY_FOREIGN_KEYS or len(refs) != len(STUDY_FOREIGN_KEYS):
            raise StudySchemaBlocked("Study Abroad owner FK/column/cascade drift")

        indexes = conn.execute(
            "SELECT ix.relname, child.relname, am.amname, "
            "ind.indisunique, (ind.indpred IS NOT NULL), "
            "(ind.indexprs IS NOT NULL), "
            "array_to_string(ARRAY(SELECT att.attname FROM "
            "unnest(ind.indkey) WITH ORDINALITY AS k(attnum, ord) "
            "JOIN pg_attribute att ON att.attrelid=child.oid "
            "AND att.attnum=k.attnum ORDER BY k.ord), ',') "
            "FROM pg_index ind "
            "JOIN pg_class ix ON ix.oid=ind.indexrelid "
            "JOIN pg_class child ON child.oid=ind.indrelid "
            "JOIN pg_namespace n ON n.oid=child.relnamespace "
            "JOIN pg_am am ON am.oid=ix.relam "
            "WHERE n.nspname='public' AND NOT ind.indisprimary "
            "AND ind.indisvalid AND ind.indisready "
            "AND ind.indnatts=ind.indnkeyatts "
            "AND child.relname IN (" + STUDY_NAMES_SQL + ")"
        ).fetchall()
        if set(indexes) != STUDY_INDEXES or len(indexes) != len(STUDY_INDEXES):
            raise StudySchemaBlocked("Study Abroad index column/structure drift")

        primary_keys = conn.execute(
            "SELECT child.relname, "
            "array_to_string(ARRAY(SELECT att.attname FROM "
            "unnest(pk.conkey) WITH ORDINALITY AS k(attnum, ord) "
            "JOIN pg_attribute att ON att.attrelid=child.oid "
            "AND att.attnum=k.attnum ORDER BY k.ord), ',') "
            "FROM pg_constraint pk "
            "JOIN pg_class child ON child.oid=pk.conrelid "
            "JOIN pg_namespace n ON n.oid=child.relnamespace "
            "WHERE n.nspname='public' AND pk.contype='p' "
            "AND child.relname IN (" + STUDY_NAMES_SQL + ")"
        ).fetchall()
        if (set(primary_keys) != STUDY_PRIMARY_KEYS
                or len(primary_keys) != len(STUDY_PRIMARY_KEYS)):
            raise StudySchemaBlocked("Study Abroad primary-key drift")

        owner_columns = conn.execute(
            "SELECT table_name, column_name, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema='public' "
            "AND table_name IN (" + STUDY_NAMES_SQL + ") "
            "AND column_name IN ('id','user_id','case_id','document_id')"
        ).fetchall()
        if (set(owner_columns) != STUDY_OWNER_COLUMNS
                or len(owner_columns) != len(STUDY_OWNER_COLUMNS)):
            raise StudySchemaBlocked("Study Abroad owner column/nullability drift")
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
