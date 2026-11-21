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
    def __init__(self, *, privileged=False):
        self.calls = []
        self.privileged = privileged

    def exec_driver_sql(self, statement):
        self.calls.append(("sql", statement))

    def execute(self, statement, parameters=None):
        if parameters is None:
            self.calls.append(("role_check", str(statement)))
            return SimpleNamespace(scalar_one_or_none=lambda: self.privileged)
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
    calls = session.connection_handle.calls
    assert calls[0][0] == "role_check"
    assert "rolbypassrls" in calls[0][1]
    assert calls[1:] == [
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


@pytest.mark.parametrize("privileged", [True, None])
def test_rls_cannot_use_a_bypass_or_unknown_database_login(monkeypatch, privileged):
    monkeypatch.setattr(settings, "TENANT_RLS_ENABLED", True)
    session = FakeSession()
    session.connection_handle = FakeConnection(privileged=privileged)
    bind_authenticated_tenant(session, "verified-user")
    with pytest.raises(RuntimeError, match="non-privileged database login"):
        _install_scoped_tenant_role(session, None, session.connection_handle)
    # No role switch and, critically, no tenant GUC assignment.
    assert [call[0] for call in session.connection_handle.calls] == ["role_check"]
