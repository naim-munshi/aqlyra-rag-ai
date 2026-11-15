"""RLS acceptance on a disposable PostgreSQL test database only.

All DDL and synthetic rows are contained in ONE SQL transaction and rolled
back, including CREATE ROLE and policy changes. No production connection.
"""
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from conftest import test_engine


_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "security" / "rls" / "tenant_runtime_policies.sql"
)


def test_tenant_rls_denies_missing_context_and_cross_user_reads_or_writes() -> None:
    assert test_engine.url.database.endswith("_test"), (
        "RLS acceptance must not run against a production database"
    )
    script = _POLICY_PATH.read_text(encoding="utf-8")
    assert script.count("CREATE POLICY aqlyra_tenant_scope") == 17
    assert "GRANT ALL" not in script
    assert "GRANT USAGE ON SCHEMA public TO aqlyra_tenant_runtime" in script
    executable_sql = "
".join(
        line for line in script.splitlines()
        if not line.lstrip().startswith("--")
    )
    assert "BYPASSRLS" not in executable_sql.replace("NOBYPASSRLS", "")

    # Disposable test_engine belongs to the isolated CI PostgreSQL database.
    with test_engine.connect() as connection:
        transaction = connection.begin()
        try:
            for statement in script.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)

            for who in ("test-tenant-one", "test-tenant-two"):
                connection.execute(
                    text("""
                        INSERT INTO public.users
                            (id, email, username, hashed_password,
                             is_active, auth_epoch, created_at, updated_at)
                        VALUES (:id, :email, :username, 'not-a-real-hash',
                                true, 0, now(), now())
                    """),
                    {
                        "id": who,
                        "email": who + "@example.invalid",
                        "username": who,
                    },
                )
                connection.execute(
                    text("""
                        INSERT INTO public.conversations
                            (id, user_id, title, mode, is_pinned,
                             created_at, updated_at)
                        VALUES (:id, :owner, 'Synthetic private chat',
                                'normal', false, now(), now())
                    """),
                    {"id": "conversation-" + who, "owner": who},
                )
                connection.execute(
                    text("""
                        INSERT INTO public.messages
                            (id, conversation_id, role, mode, content, created_at)
                        VALUES (:id, :conversation_id, 'user', 'normal',
                                'synthetic - no customer data', now())
                    """),
                    {"id": "message-" + who,
                     "conversation_id": "conversation-" + who},
                )
                connection.execute(
                    text("""
                        INSERT INTO public.memories
                            (id, user_id, kind, content, normalized_content,
                             importance, confidence, is_active,
                             created_at, updated_at)
                        VALUES (:id, :owner, 'fact', 'synthetic',
                                'synthetic', 0.5, 1.0, true, now(), now())
                    """),
                    {"id": "memory-" + who, "owner": who},
                )

            # Exercise the actual non-owner role; owner/BYPASSRLS tests are invalid.
            connection.exec_driver_sql(
                "SET LOCAL ROLE aqlyra_tenant_runtime"
            )
            assert connection.execute(text(
                "SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )).scalar_one() is False

            # No authenticated actor context -> fail closed.
            connection.execute(text(
                "SELECT set_config('aqlyra.tenant_user_id', '', true)"
            ))
            for table in ("users", "conversations", "messages", "memories"):
                assert connection.execute(
                    text("SELECT count(*) FROM public." + table)
                ).scalar_one() == 0

            # Tenant one sees only their records, including child messages.
            connection.execute(text(
                "SELECT set_config('aqlyra.tenant_user_id', "
                "'test-tenant-one', true)"
            ))
            for table in ("users", "conversations", "messages", "memories"):
                assert connection.execute(
                    text("SELECT count(*) FROM public." + table)
                ).scalar_one() == 1

            # An explicit attempt to UPDATE the other tenant silently affects no row.
            other = connection.execute(text(
                "UPDATE public.conversations SET title = 'bad' "
                "WHERE id = 'conversation-test-tenant-two'"
            ))
            assert other.rowcount == 0

            # WITH CHECK rejects writes forged with another tenant's user_id.
            connection.exec_driver_sql("SAVEPOINT rls_expected_reject")
            with pytest.raises(DBAPIError):
                connection.execute(text(
                    "INSERT INTO public.conversations "
                    "(id, user_id, title, mode, is_pinned, "
                    "created_at, updated_at) "
                    "VALUES ('forged-rls', 'test-tenant-two', 'forged', "
                    "'normal', false, now(), now())"
                ))
            connection.exec_driver_sql(
                "ROLLBACK TO SAVEPOINT rls_expected_reject"
            )
            connection.exec_driver_sql("RELEASE SAVEPOINT rls_expected_reject")

            # Change the transaction-local actor only for test assertion.
            connection.execute(text(
                "SELECT set_config('aqlyra.tenant_user_id', "
                "'test-tenant-two', true)"
            ))
            assert connection.execute(text(
                "SELECT id FROM public.conversations"
            )).scalar_one() == "conversation-test-tenant-two"
        finally:
            # Rolls back synthetic rows, policies, grants, and the test role.
            transaction.rollback()
