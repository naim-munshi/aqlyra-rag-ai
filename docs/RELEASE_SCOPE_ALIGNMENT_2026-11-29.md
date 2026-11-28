# Aqlyra release-scope alignment — 29 November 2026

## Decision

Study Abroad is part of Aqlyra's unified product and this release candidate. Its API, models, schemas, services, migration `d4ec2f9b7860`, tests, authenticated frontend route, and workspace UI are included.

Candidate branch: `release/study-abroad-included-20261129`.

The existing branch name `release/core-without-study-abroad-20261027` is legacy naming only. Do not infer feature exclusions from the branch name or older documentation.

## Reconciliation completed in this candidate

- Replaced the core-only release scope with an explicit Study-Abroad-included scope contract.
- Updated release acceptance requirements to include the Study Abroad migration and two-account evidence/privacy E2E.
- Updated Railway staging validator to expect this candidate branch and stopped incorrectly rejecting Study Abroad as a deferred feature.
- Updated release gate default branch and its unit-test expectation.
- Updated GitHub ruleset documentation to match the last observed active ruleset state: 11 required job contexts are present, but required approving reviews are set to zero.
- Updated README and backend handoff text to distinguish source scope from actual deployed state.
- Restored the authenticated Study Abroad page, bounded BFF API proxy, workspace UI, sidebar navigation, and feature documentation into the candidate; changed the upload error copy to avoid a deployment-specific file-size promise.
- Added explicit WEB_RESEARCH_ENABLED/provider configuration requirements to the staging validator and production env template; research remains default-off until staging acceptance.
- Made the release gate require exact release-branch protection and a dedicated ruleset; added tests for branch patterns, required checks and fail-closed behaviour. Enabled all required release workflows on `release/**`.
- Recorded that advanced Study Fit, Program Research and Evidence Brief APIs are not yet exposed by dedicated UI controls.

## Remaining blockers not safely changeable from this code PR

| Area | Last observed state | Required action |
|---|---|---|
| GitHub rulesets | Main ruleset ID `25905480` has 11 job contexts but approvals = 0; no dedicated release-branch ruleset is verified | Admin must add at least one independent approval to main and create an active `release/**` ruleset with 13 release contexts; `release_gate.py` now fails closed until both are enforced |
| Render backend | Live deployment SHA/workspace not freshly accessible | Confirm exact deployed commit, migration head, API health, provider connectivity |
| Neon database | Live schema/role/RLS not accessible through current connector | Confirm current Alembic head, owner isolation, production role and RLS policies |
| Railway staging | Only `aqlyra-voice-worker` present and Offline; no full stack | Provision/verify API, frontend, PostgreSQL/pgvector, Redis and private storage |
| Study Abroad | Student Journey UI restored; advanced Study Fit / Program Research / Evidence Brief routes are API-only, not surfaced in the current UI; production journey not independently accepted | Run source-grounded research, case CRUD, file/evidence ownership and two-user privacy E2E; decide whether to add dedicated UI for advanced APIs |
| Agent Harness | PRs #235–#237 merged on release line; feature defaults OFF | Apply only additive migration on restored disposable DB, set explicit model prices, canary allowlist and test budget/trace privacy |
| Voice | Railway worker Offline | Restore worker under reviewed config, then run a real LiveKit room/audio/STT/TTS test |
| Backup/restore | Off-host encrypted DB + object restore not verified | Perform separate encrypted export and isolated restore rehearsal with RPO/RTO |
| Production rollout | Not approved by this candidate | Independent review, exact-head checks, staging acceptance and explicit owner approval |

## Safety boundary

This alignment changes source-control scope and release validation only. It does not modify production databases, Render settings, Railway services, Vercel environment variables, credentials, user data, or production deployment aliases. No production migration or deployment is authorized by this change.

## Evidence references

- [PR #235 — readiness migration support](https://github.com/naim-munshi/aqlyra-rag-ai/pull/235)
- [PR #236 — Agent Harness production-line port](https://github.com/naim-munshi/aqlyra-rag-ai/pull/236)
- [PR #237 — Agent Harness canary allowlist](https://github.com/naim-munshi/aqlyra-rag-ai/pull/237)
- [GitHub ruleset](https://github.com/naim-munshi/aqlyra-rag-ai/rules/25905480)
- [Release acceptance](RELEASE_ACCEPTANCE.md)
- [Unified release scope](CORE_RELEASE_SCOPE.md)
