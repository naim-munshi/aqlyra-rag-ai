# Aqlyra — Phase 0–10 release acceptance checkpoint (2026-10-29)

This is a **release engineering ledger**, not authorization to remove Vercel SSO, merge `main`, expose guest traffic, charge a provider or reset production data. It complements `FULL_RELEASE_PRODUCTION_CUTOVER.md` and Issue #34. Recheck exact HEAD and service state on every rollout.

## Work order and current result

| Phase | Scope | Code / smoke evidence | Live acceptance |
| --- | --- | --- | --- |
| 0 | Preserve existing FastAPI, pgvector and hybrid RAG architecture | PASS: release branch retains original models and routing | PASS for non-destructive architecture review |
| 1 | Authentication/session, SQLi, SSRF, least privilege and tenant isolation | Source unit/security tests PASS on previous HEAD | BLOCKED: production DB restricted role and RLS, independent two-user tests |
| 2 | Render Core/Vercel Full + Redis/Neon | LIVE on protected frontend and Core backend | PARTIAL: Full backend cutover not authorized |
| 3 | Gmail OTP, Google sign-in, password-reset auto-login | Recovery patches and email send logs improved | PARTIAL: two real inboxes, Google browser consent and signed-in cookie E2E |
| 4 | Anonymous guest chat and admin IP traffic | Bounded signed proxy, Redis quota and 24h audit implemented | OFF: Full backend, real rate limits, legal notices, protection policy and cost gates |
| 5 | Converse + Knowledge RAG | Hybrid evidence/citation enforcement and 402 error classification tested | FAIL: live Hugging Face embedding quota HTTP 402 pending provider resolution |
| 6 | AI Files and private document storage | DOCX/XLSX/PPTX/PDF/MD tests, synthetic object-store restart | BLOCKED: private real object ACL, existing local file recovery, multi-process restart |
| 7 | Study Abroad | Scoped API and read-only live workflow probes PASS | PARTIAL: actual signed-in case, uploads, nationality-specific official-source QA |
| 8 | LiveKit voice and iPhone mic | Worker safety, microphone teardown and fail-closed status tests | OFF: healthy named worker, paid/quota checks, EN/JA/BN audio end-to-end |
| 9 | Monitoring / recovery | Health/readiness, protected admin, synthetic PG18 restore | PARTIAL: alert ownership, Full off-host backup+isolated restore, retention policy |
| 10 | Independent security review, release approval | GitHub CI strong on previous exact heads | BLOCKED: all external gates and reviewer approval |

## Exact infrastructure observations (read-only, 29 October 2026)

- Repository `naim-munshi/aqlyra-rag-ai`: `main` remains at `6bd16d5`, PR #36 Core and PR #37 Full are unmerged. The latest observed **pre-document-change** Core commit was `7065846` with 7/7 workflows passing; Full was `bb57298` with 8/8 passing. Revalidate after this file is committed.
- Render `srv-dbgjt0ei0phs73akd8j0` deployment `dep-dbhikgdg1s2s73a67sng` LIVE at Core `7065846`; auto-deploy OFF; Full backend is not live.
- Vercel `aqlyra` frontend deployment `dpl_877tonsouExdkZCWqAPWdDgB6r76` READY from Full `bb57298`; aliases `aqlyra-ai.vercel.app` and `aqlyra-navy.vercel.app`; SSO protection ON. `aqlyra.vercel.app` is assigned to a different project/team, not this project.
- Neon production `rough-river-66110449`, `neondb` PostgreSQL 18.6, Alembic `d4ec2f9b7860`: 20 public ordinary tables, **0 RLS-enabled**, only database owner `neondb_owner` listed by project role API. Current snapshot schedule is empty; three recovery/schema branches and an older snapshot remain. None prove a new off-host Full-data restore.
- Live Vercel and provider acceptance must not be inferred from source CI or a protected frontend's READY status.

## P0: database public launch gate (non-destructive)

The new `scripts/ops/production_db_isolation_gate.py` performs a **read-only** audit of a future restricted application's direct Neon connection; it never creates a role, applies a policy or migrates data. It requires:

1. Current Full Alembic revision and all 19 protected tenant tables.
2. A non-owner, non-superuser, non-`BYPASSRLS` runtime role.
3. RLS enabled **and at least one policy** on every protected tenant table; each table owned by a distinct role.
4. An owner-only private file containing the direct TLS Neon runtime URL; host, database and role must be independently confirmed.

On the trusted owner machine after staging RLS design, create a `0600` private runtime-URL file without disclosing its contents and run:

```sh
python3 scripts/ops/production_db_isolation_gate.py \
  --runtime-url-file "$HOME/.aqlyra/private/runtime-neon-url" \
  --expected-host "<DIRECT-NEON-HOST-FROM-DASHBOARD>" \
  --expected-role "<RESTRICTED-APP-ROLE>"
```

`DB_ISOLATION_GATE=PRELIMINARY_PASS` would prove only catalog/role prerequisites. A permissive or wrong policy can still pass the catalog check. **Mandatory additional proof**: on a restored isolated branch, run transactional identity-context tests for SELECT/INSERT/UPDATE/DELETE, empty identity, two distinct users, all join and child tables, RAG retrieval, auth bootstrap, background jobs, Study Abroad, artifacts and cross-tenant 404s. In particular, registration/Google login/reset need a separately reviewed privileged auth path; blindly enabling RLS on `users` can break or weaken auth. Do not use a universal `USING (true)` policy or treat caller-supplied user IDs as trusted.

RLS policy design must run on staging with a restricted role first; after off-host backup/restoration and independent security approval, schedule a separate owner-controlled production change. The current database must **not** be modified to make the gate green.

## Next acceptance sequence

1. Resolve the real embedding credit/quota with the provider or an owner-approved same-model serving endpoint. **Do not** mix vectors from a different model into existing pgvector indexes or enable deterministic production embeddings.
2. Complete Full-schema off-host encrypted `pg_dump` and network-isolated PG18 restore plus private uploaded-file/object manifest. Do not downgrade the already migrated Full production schema.
3. Design/test RLS and least-privilege with the new offline catalog gate and independent two-tenant negative tests.
4. Verify durable object storage for existing user documents and generated artifacts, signed ACLs and restart persistence.
5. Perform real Google/OTP/password-reset session tests, signed-in document/RAG/Study Abroad/AI Files and browser-mobile QA on the **protected** production app.
6. Provision and health-check the named LiveKit worker with owner-private credentials, then test real English/Japanese/Bangla STT→RAG→TTS and disconnected/unavailable cases before enabling the voice flag.
7. After exact-HEAD CI and independent reviewer approval, change Render from Core to Full only through an approved controlled cutover. Accept guest signed proxy/Redis quotas, privacy/traffic monitoring, then explicitly choose the Vercel public access policy.
8. Keep `main`, Vercel SSO, Guest OFF, Voice OFF, existing backups and database untouched until every necessary release gate is recorded.

**Do not mark public production PASS solely from this ledger or the preliminary DB catalog gate.**
