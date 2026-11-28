# Aqlyra unified release scope — Study Abroad included (2026-11-29)

## Source control and product scope

- **Unified release candidate:** `release/study-abroad-included-20261129`.
- **Base source line:** `release/core-without-study-abroad-20261027`, after the bounded Knowledge Agent production-line port (PR #236), canary user allowlist (PR #237), and readiness support (PR #235).
- **Study Abroad is INCLUDED** in this release candidate: API routers, models, schemas, services, migration `d4ec2f9b7860`, tests, authenticated Next.js route, and workspace UI.
- The legacy branch name `release/core-without-study-abroad-20261027` is historical. Its name and older documents do not override this product-scope decision.
- **Also included:** Converse, Knowledge ingestion/indexing, semantic and lexical retrieval, RRF fusion, Auth/session controls, AI Files, Web Research, Agent Harness (disabled by default), and the Browser Agent in disabled/fail-closed mode.
- Study Abroad is an evidence-assistance workflow, not a guarantee of admission, visa approval, legal eligibility, or current programme availability. Every recommendation must retain source provenance, freshness, user ownership, and explicit uncertainty.
- No deletion or alteration of current production user data, credentials, uploads, document schemas, embeddings, or migration history is authorized by this scope change.

## Required integration invariants

1. The backend router must register Study Abroad endpoints and all associated models must be included in SQLAlchemy/Alembic metadata.
2. The migration chain must contain `d4ec2f9b7860` and be rehearsed on a restored disposable database before any production migration.
3. The authenticated frontend route and workspace must call the same backend API contract that is tested in staging.
4. Study Abroad cases, requirements, evidence, uploads, and generated briefs must be owner-scoped. Two independent accounts must not read, mutate, or infer each other's records.
5. Program research must preserve source URLs, retrieval time, evidence excerpts, and unsupported-claim abstention. No visa/admission outcome may be represented as guaranteed.
6. Readiness must verify all required Study Abroad schema objects when the feature is part of the release.
7. CI and staging gates must validate this exact candidate SHA; a green check on another branch or old SHA is not acceptance.

## Release safety

- Do not merge the candidate into protected `main` or deploy it solely because this branch exists or automated CI passes.
- Do not apply migrations to the production database as part of branch alignment.
- Never run `alembic downgrade` or delete production rows to reconcile release scope.
- If a disposable staging database has an incompatible migration history, rebuild only that disposable database from a clean/verified fixture.
- Agent Harness remains default-off. Enable only for explicit canary user IDs after database migration, model pricing, budget, and owner-isolation acceptance.
- Browser Agent remains disabled until OS/container isolation and network egress controls are independently verified.

## Acceptance sequence

1. Verify GitHub protections, exact-head required checks, and independent review policy.
2. Build isolated staging with API, frontend, PostgreSQL/pgvector, Redis, and private persistent storage.
3. Rehearse all migrations, including Study Abroad and Agent Harness, on a restored disposable database.
4. Run two-account Auth, conversation, document, artifact, and Study Abroad privacy E2E.
5. Run provider-backed multilingual RAG, source-grounded Study Abroad research, citations, and unsupported-question tests.
6. Accept AI Files exports, Office/PDF rendering, and cloud storage lifecycle.
7. Keep Browser Agent disabled unless sandbox and egress acceptance passes; verify Voice only with an active LiveKit worker and a real audio session.
8. Verify off-host encrypted database/object backup and a separate restore rehearsal with RPO/RTO.
9. Obtain independent release review and explicit owner approval before controlled production rollout.

See [release acceptance](RELEASE_ACCEPTANCE.md), [GitHub ruleset setup](GITHUB_RULESET.md), and [the Railway staging validator](../scripts/ops/railway_staging_gate.py).
