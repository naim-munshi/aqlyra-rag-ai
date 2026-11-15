# Aqlyra tenant RLS — staged production rollout

Date: 2026-11-16. **Status: STAGED / NOT ACTIVE IN PRODUCTION.**

## Verified live baseline
- Neon PostgreSQL 18.7; pgvector 0.8.7.
- 20 public application tables, no RLS policies previously installed.
- The connected `neondb_owner` has `rolbypassrls=true`. Postgres bypasses all RLS policies for this role, even with `FORCE ROW LEVEL SECURITY`. Merely enabling RLS while remaining connected as this role DOES NOT protect tenant data.
- The current API uses `SessionLocal` for authenticated requests, unauthenticated account lifecycle and the global document indexing worker. Changing all queries to tenant-scoped policies without separation would break legitimate background work.
- Public-table privileges are not granted to PUBLIC, and owner-filtering tests exist, but neither substitutes for database-enforced tenant isolation.

## Staged changes

1. `backend/security/rls/tenant_runtime_policies.sql`: explicit no-login/no-BYPASSRLS runtime role; table-specific SELECT/DML grants; fail-closed `USING` plus `WITH CHECK` policies across 17 private parent/child tables. Token secrets and migration tables remain out of the restricted role.
2. `TENANT_RLS_ENABLED` defaults to **false**. When enabled only after the SQL is applied, the verified JWT subject is bound to the SQLAlchemy session before its first query. Each PostgreSQL transaction runs `SET LOCAL ROLE aqlyra_tenant_runtime` followed by a transaction-local `set_config('aqlyra.tenant_user_id', subject, true)`. Rollback/commit closes the tenant context, including with Neon transaction pooling.
3. Admin-role reset happens only after the existing immutable user-ID allowlist passes. Background indexing and unauthenticated authentication workflows remain owner-scoped.
4. The real PostgreSQL 16/18 CI acceptance test runs SQL policies and synthetic two-tenant reads/writes in one transaction, then rolls everything back.

## Mandatory gates BEFORE production activation

- CI: all backend tests; two-user HTTP/RAG tests; cross-user document, chunk, memory, conversation, message, project, study-abroad and cloud upload operations; administrator user management and background indexing.
- Neon: take/verify a recoverable snapshot and test the SQL against a disposable Neon branch. Check all 17 policies, the role has `rolbypassrls=false`, and row counts/embedding coverage are unchanged.
- Use `SELECT current_user, current_setting('aqlyra.tenant_user_id', true)` from a scoped transaction to verify that the effective role is **not** `neondb_owner`. An owner-only test is NOT evidence RLS works.
- Any tenant session that starts SQL before the JWT subject is bound must fail closed and be fixed in code before enabling the feature.
- Verify a separate **non-BYPASSRLS login role and connection URL for ordinary application requests**. The present approach switches roles inside a privileged owner connection and is transitional defense-in-depth, not a complete least-privilege production separation. Full protection requires that compromised application SQL cannot `RESET ROLE` to an owner with `BYPASSRLS`.
- Keep a privileged role only for explicitly authorized admin and indexing operations. Do not reveal it to users, browsers, or arbitrary agent SQL. Audit what queries are allowed through privileged paths.
- Roll out behind `TENANT_RLS_ENABLED` on a staging backend after database migration, then after full acceptance to production during a controlled window. Never run raw policy SQL against live Neon simply because static tests pass.
- Rollback: disable the opt-in application setting; restore the previous backend deployment. Do not drop policies or roles without separately verifying active connections and a data-preserving rollback.

## Why this is not called completed

The existing Render API still connects through a privileged database role and requires a staged, provider-backed role/credential rotation to make Postgres RLS a security boundary. No changes to production credentials, RLS policy state, tenant data or account ownership have been made by this PR.
