# Aqlyra core release scope — Study Abroad deferred (2026-10-27)

## Source control and scope

- **Core candidate:** `release/core-without-study-abroad-20261027`,
  created as a clean branch from the protected `main` release base.
- **Source of integration:** the verified code snapshot of Draft PR #35,
  commit `6458786dc1c79b549ebc0800f936fbc127d8e2f7`.
- **Excluded**: all Study Abroad API, models, business logic, schemas,
  migration `d4ec2f9b7860`, tests, Next.js route and UI.
  The authenticated /study-abroad page and /api/v1/study-abroad APIs must
  respond 404 rather than being displayed or operating unexpectedly.
- **Included**: existing RAG document ingestion, indexing, embeddings,
  pgvector schema and hybrid retrieval; auth and revocation fixes; AI Files;
  Web Research; the Browser Agent in disabled/fail-closed production mode;
  all security and release-gate fixes.
- **No deletion or alteration of current production user data**, migrations,
  uploads, document schemas, embeddings or credentials.
- **README.md is byte-for-byte identical** to the latest full candidate;
  it remains a pre-production overview, not a live-service guarantee.

Study Abroad is preserved on its feature/integration branches for a later
separate review. Do not copy a mixed Study Abroad database migration into
this release or attempt to run `alembic downgrade` against real user data
to exclude that feature. If a *staging* database already applied the
deferred revision, use a fresh disposable staging database rather than
a destructive downgrade. Never delete live data to adjust scope.

## Merge controls

A user authorized merging the **core except Study Abroad**. Actual merge
must still satisfy the active GitHub `main` Ruleset: independent review,
the required 11 CI job checks on the exact head, no stale approvals, and
the release acceptance requirements in `docs/RELEASE_ACCEPTANCE.md`.
Do not bypass this Ruleset; do not merge the old mixed Draft PR #33/#35
by accident. Production deployment is separately gated.

## Phase sequence

1. GitHub main protection verified.
2. Staging infrastructure: currently incomplete. Existing Railway
   `Aqlyra-Staging` has uncommitted backend + pgvector service drafts but
   no confirmed live deployment, private volumes, Redis or frontend.
   Select a host design and verify disposable, persistent, isolated
   staging before real acceptance.
3. Auth/session/privacy real E2E using at least two staging accounts.
4. LLM-backed semantic RAG grounding, citations and tenant-isolation
   acceptance.
5. AI Files exports and Office/PDF multilingual reviews, **excluding**
   Study Abroad.
6. Browser/renderer worker isolation (or Browser Agent remains disabled).
7. Off-host encrypted backup + tested restore, documented RPO/RTO.
8. Independent release review, gradual deploy, live smoke, alerts
   and rollback.

See `docs/GITHUB_RULESET.md` and Issue #34 for remaining evidence.
