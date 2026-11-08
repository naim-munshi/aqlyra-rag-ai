# Repository hygiene audit — 2026-11-08

**Read-only inventory, plus deliberately separate CI/docs remediation PRs.** These counts are an audit-time snapshot, not a continuous GitHub monitor.

## Active release sources — preserve

| Role | Ref |
|---|---|
| Protected repository baseline | `main` |
| Render FastAPI production | `release/core-without-study-abroad-20261027` |
| Vercel Next.js production | `fix/center-empty-chat-composer-20261102` |
| Live demo | https://aqlyra-ai.vercel.app |

The source tree is **not** one synchronized branch: backend release was **451 commits ahead** of `main`, frontend release was **533 ahead**; the two production refs had diverged. **Do not force-merge these branches or use a branch delete to synchronize them** without an independently tested integration release.

Repository audit snapshot: 140 remote branches, 50 open pull requests (39 draft, 11 ready) before the incremental cleanup PR was opened, and **90 branches without an open PR**. Tracked snapshots contained 370 files in `main`, 657 in the backend release and 652 in the frontend release. The tree audit found no tracked `.env` secrets, dependency/vendor trees, build folders or release ZIPs in those branch snapshots. This **does not establish absence of exposed credentials in commit history**.

## Confirmed CI repair: do not delete the tests

The 2026-11-08 backend release failed two separate checks: `Always-on Merge Gate` (run 42474836848) and `Frontend and Deployment Checks` (run 42474836811). Both errors originated from `scripts/ops/test_ephemeral_chat_load.py` importing `pytest` during offline stdlib `unittest` discovery. Backend test, security, dependency, ARM64, documentation and embedding-worker checks had passed. Preserve the **safety benchmark**; convert the test to stdlib `unittest` rather than removing it or relaxing production restrictions. Rebasing the reviewed fix onto the current release is tracked in [PR #164](https://github.com/naim-munshi/aqlyra-rag-ai/pull/164). The older competing PRs #148 and #150 were **closed as superseded**, with explanatory comments, after [PR #164](https://github.com/naim-munshi/aqlyra-rag-ai/pull/164) was merged at commit `4d5d8c8f5e4edb7a63b11e3397b2ee871979c3d3`. The standalone no-pip gate and all PR-head security/dependency/backend checks passed.

## Remote branches: verified fully integrated, deletion candidates only

GitHub commit comparison showed **zero commits ahead** of the deployed branch for each of the following. Each was also absent from the open PR head inventory at audit time. These are **candidates** for a separate local/remote-worktree and deployment-reference check, **not authorization to force-delete a checked-out or referenced branch**:

| Branch | All commits contained in |
| --- | --- |
| `feat/temporary-ephemeral-artifact-testing-20261108` | backend release |
| `fix/automatic-public-live-followups-20261108` | backend release |
| `fix/web-research-groq-rate-limit-fallback-20261108` | backend release |
| `fix/rag-skip-unindexed-semantic-20261108` | backend release |
| `fix/rag-bounded-semantic-backfill-20261108` | backend release |
| `fix/readiness-study-fit-head-20261108` | backend release |
| `security/render-api-hsts-20261108` | backend release |
| `security/release-ci-audit-gates-20261108` | backend release |
| `security/private-bff-json-cache-20261108` | frontend release |
| `fix/auth-bff-timeouts-20261108` | frontend release |

**Before any deletion:** confirm `git worktree list` locally, no other active CI/deployment/external git ref points to the branch, confirm the current production target SHA and `git merge-base --is-ancestor` against that target, confirm no open PRs, retain any branch required as an audit trail. Use ordinary branch deletion only, **never `--force` or a rewritten ref**.

The current GitHub connector can compare, create and update refs/PRs, but does not expose a branch-ref **delete** action. Accordingly, no remote branches were deleted by this audit.

## PR triage

- **Closed as superseded:** #148 and #150, both covered by merged #164 (no feature code removed).
- **Keep:** #36 (main promotion candidate), #101 (frontend release lifecycle), #37 (full/Study Abroad candidate), #147 and #149 (main dependency remediation), #151/#152 (RAG quality/evaluation), #153 (frontend login handling) and #129 (Study Abroad UI). These contain unique commits relative to their intended target or still require a production-specific integration decision.
- **Other 39 draft/ready PRs:** every open head inspected had commits not contained by its *current target branch*; being older or present in a different branch is insufficient proof it can be closed safely.
- Do not combine #147/#149 or #148/#150 via blind simultaneous merge; review the exact-file diffs and accept one coherent change set into the intended target.

## Docs: retain provenance, fix the front door

The [README](../README.md) now shows the **Nov 8** operational caveats before its Oct 31–Nov 2 historical capability matrix. Historical reports `PRODUCTION_STATUS_2026-10-31.md`, `CORE_RELEASE_SCOPE.md`, incident notes and acceptance runbooks are **auditable historical evidence**, not junk files; preserve them and mark as dated rather than silently deleting. In particular, source-code implementation, synthetic CI, and authenticated live-user acceptance are different evidence levels.

## Remaining housekeeping gates

1. Verify the two previously failed **push** checks against merge commit `4d5d8c8f`; Always-on Merge Gate passed on the new head, while the broader checks were still running at the audit update.
2. Superseded duplicate PRs #148 and #150 were closed with reasons; continue leaving unique draft work reviewable.
3. Perform the 10-branch candidate worktree/deployment-reference check in an environment with authorized **delete ref** support.
4. Consolidate releases through a separate branch-specific integration test campaign, not during cleanup.
5. Review dependency advisories and repository permissions/rulesets; the managed integration cannot read all branch-protection administration details.

**No customer documents, embeddings, private storage, API keys, migrations, deployment secrets, or active release branches should be altered as part of hygiene cleanup.**
