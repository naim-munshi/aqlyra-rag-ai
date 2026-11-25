"""Safe diagnostics for the durable knowledge-index worker."""
from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

from app.services.knowledge_index_queue import safe_worker_error_diagnostics


def test_worker_diagnostics_expose_only_valid_sqlstate_and_connection_flag() -> None:
    exc = OperationalError(
        "SELECT private customer content",
        {"credential": "must-not-be-logged"},
        SimpleNamespace(sqlstate="25006", pgcode="25006"),
        connection_invalidated=True,
    )

    diagnostics = safe_worker_error_diagnostics(exc)

    assert diagnostics == {
        "sqlstate": "25006",
        "connection_invalidated": True,
    }
    assert "private" not in repr(diagnostics)
    assert "credential" not in repr(diagnostics)
    assert "must-not-be-logged" not in repr(diagnostics)


def test_worker_diagnostics_support_psycopg2_pgcode_fallback() -> None:
    exc = OperationalError(
        "query text is private",
        {},
        SimpleNamespace(pgcode="08006"),
    )

    assert safe_worker_error_diagnostics(exc) == {
        "sqlstate": "08006",
        "connection_invalidated": False,
    }


def test_worker_diagnostics_do_not_accept_arbitrary_or_malformed_codes() -> None:
    for value in ("2500", "25006-secret", "ABCDE!", 25006):
        exc = OperationalError(
            "private",
            {},
            SimpleNamespace(sqlstate=value),
        )
        assert safe_worker_error_diagnostics(exc) == {
            "sqlstate": "unavailable",
            "connection_invalidated": False,
        }


def test_non_database_exception_does_not_expose_exception_message() -> None:
    exc = RuntimeError("private database URL and user data")

    diagnostics = safe_worker_error_diagnostics(exc)

    assert diagnostics == {
        "sqlstate": "unavailable",
        "connection_invalidated": False,
    }
