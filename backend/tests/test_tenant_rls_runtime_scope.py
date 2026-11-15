"""Opt-in tenant SQL session behavior; does not activate production RLS."""
from types import SimpleNamespace

import pytest

from app.config.settings import settings
from app.database.connection import (
    _install_scoped_tenant_role,
    bind_authenticated_tenant,
    permit_verified_admin_scope,
)


class FakeConnection:
    def __init__(self):
        self.calls = []

    def exec_driver_sql(self, statement):
        self.calls.append(("sql", statement))

    def execute(self, statement, parameters):
        self.calls.append(("params", str(statement), parameters))


class FakeSession:
    def __init__(self, *, open_transaction=False):
        self.info = {}
        self.open_transaction = open_transaction
        self.connection_handle = FakeConnection()

    def in_transaction(self):
        return self.open_transaction

    def connection(self):
        return self.connection_handle


def test_disabled_mode_never_changes_existing_database_transactions(monkeypatch):
    monkeypatch.setattr(settings, "TENANT_RLS_ENABLED", False)
    session = FakeSession()
    bind_authenticated_tenant(session, "user-1")
    _install_scoped_tenant_role(session, None, session.connection_handle)
    permit_verified_admin_scope(session)
    assert session.info == {}
    assert session.connection_handle.calls == []


def test_auth_scopes_role_before_query_and_rejects_identity_switch(monkeypatch):
    monkeypatch.setattr(settings, "TENANT_RLS_ENABLED", True)
    session = FakeSession()
    bind_authenticated_tenant(session, "user-1")
    _install_scoped_tenant_role(session, None, session.connection_handle)
    assert session.connection_handle.calls == [
        ("sql", "SET LOCAL ROLE aqlyra_tenant_runtime"),
        (
            "params",
            "SELECT set_config('aqlyra.tenant_user_id', :id, true)",
            {"id": "user-1"},
        ),
    ]
    # Idempotent for the same verified token subject.
    bind_authenticated_tenant(session, "user-1")
    with pytest.raises(RuntimeError, match="before opening"):
        bind_authenticated_tenant(session, "user-2")


def test_tenant_subject_must_be_bound_before_transaction(monkeypatch):
    monkeypatch.setattr(settings, "TENANT_RLS_ENABLED", True)
    session = FakeSession(open_transaction=True)
    with pytest.raises(RuntimeError, match="before opening"):
        bind_authenticated_tenant(session, "user-1")
    with pytest.raises(ValueError, match="nonempty"):
        bind_authenticated_tenant(FakeSession(), "")


def test_unscoped_background_worker_does_not_claim_automatic_rls(monkeypatch):
    monkeypatch.setattr(settings, "TENANT_RLS_ENABLED", True)
    session = FakeSession()
    _install_scoped_tenant_role(session, None, session.connection_handle)
    assert session.connection_handle.calls == []


def test_admin_override_only_after_identity_verified(monkeypatch):
    monkeypatch.setattr(settings, "TENANT_RLS_ENABLED", True)
    session = FakeSession(open_transaction=True)
    with pytest.raises(RuntimeError, match="verified"):
        permit_verified_admin_scope(session)

    session = FakeSession(open_transaction=False)
    bind_authenticated_tenant(session, "approved-admin")
    session.open_transaction = True
    permit_verified_admin_scope(session)
    assert session.info["aqlyra_rls_verified_admin"] is True
    assert session.connection_handle.calls == [("sql", "RESET ROLE")]
    _install_scoped_tenant_role(session, None, session.connection_handle)
    assert session.connection_handle.calls == [("sql", "RESET ROLE")]
