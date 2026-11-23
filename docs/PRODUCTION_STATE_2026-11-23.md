# Aqlyra production state — 23 November 2026

**Review date:** 23 November 2026 (JST)  
**Classification:** Deployed engineering beta; not enterprise-production certified.  
**Purpose:** Reconcile the active Vercel, Render and GitHub release lines. This is a point-in-time operational record, not an uptime guarantee.

## Scope and verification limits

This review inspected the connected GitHub repository and pull requests, the active repository ruleset, the Vercel `aqlyra` project and its production deployment record, Render service configuration, recent deployment records and selected application logs. GitHub Actions results were read for the exact commits identified below. A fresh live Neon catalog query of production roles and table RLS flags was not completed in this review; the RLS classification below is based on the staged release PR and its explicit rollout notes. No SQL statement was run.

A fresh independent browser-to-API authenticated user journey was not completed in this review. Direct public HTTP probes from the review environment were not conclusive. Consequently, provider deployment state and selected log evidence must not be described as an independently certified end-to-end uptime or user-journey test.

No production database, user records, secrets, environment variables, service settings, LiveKit project, or production deployment was changed during this review.

## 1. Deployed release topology

| Component | Provider state | Source branch and revision | Operational evidence and limits |
| --- | --- | --- | --- |
| Frontend | Vercel production deployment `READY` | `fix/center-empty-chat-composer-20261102` · `e2c15a92815edc47c8f9975dfd4fee451422d080` | Project `aqlyra`; verified domain `aqlyra-ai.vercel.app`. The deployment commit retires the public scripted demo; `/demo` requires sign-in. |
| Core API | Render deployment `live` | `release/core-without-study-abroad-20261027` · `1f8bbc8d0cc70e0d2162335e7d762f6f1e03123c` | Render Free, Singapore. Latest deploy `dep-dc1j3vmq1p3s738buuq0`. Auto-deploy is OFF. |
| Semantic worker | Render deployment `live` | `release/core-without-study-abroad-20261027` · `28542fec4d10fb8e3e65a85a83ca90c929f66c7f` | Render Free, Singapore. Latest deploy `dep-dc1io7d6e07s73dg4ah0`. Auto-deploy is OFF. This is the embedding worker, not a LiveKit voice agent. |

The frontend and backend intentionally deploy from different branches. The backend source embedded in the frontend branch is not automatically the deployed backend. Do not merge the branches wholesale or assume that the GitHub default branch represents production.

### Recent Render log evidence

At approximately **23 November 2026, 08:51 JST**:

- The Core API logged application startup completion and a successful `GET /` response (HTTP 200).
- Its startup diagnostics reported `voice_api_startup_ready=true` and `voice_provider_auth_probe result=PASS`.
- The API reported the intended LiveKit dispatch host as `aqlyra-whhfocpe.livekit.cloud`.
- The semantic worker logged startup completion and a `GET /health` response (HTTP 200).

This supersedes the older 2 November note that the API lacked LiveKit credentials. It proves the API-side provider-authentication probe passed at that startup, **not** that a LiveKit agent joined a room or that a real microphone/audio call succeeded.

Both Render services currently have an empty `healthCheckPath` in their service configuration. Configure liveness checks in the Render Dashboard:
- Core API: `/api/v1/health`
- Semantic worker: `/health`

Use liveness endpoints for process health. Do not use the dependency-heavy readiness endpoint as a restart/liveness probe.

The reviewed Render log windows did not establish the cause of the earlier intermittent HTTP 503 reports. A missing 503 entry in a bounded log query is not proof that no 503 occurred outside that window. Render Free cold starts are a plausible operational risk, but the available evidence does not prove they caused the incidents.

## 2. Knowledge ingestion and retrieval evidence

### Index coverage

The last recorded production indexing audit (10 November 2026) reported:

- **1,035 / 1,035** eligible Knowledge chunks with matching 384-dimensional vectors for the deployed static multilingual encoder.
- **7 answer-key chunks** quarantined and excluded from retrieval.

This is index/vector coverage. It does not measure ranking quality, correct answers, citation entailment, or end-to-end reliability.

### Offline multilingual dense-retrieval evaluation

The deployed-weight Aqlyra static 384D ONNX encoder was evaluated on 60 synthetic queries over 30 English-source chunks. Reported Hit Rate@1:

| Query language | Hit Rate@1 |
| --- | ---: |
| English | 70% |
| Japanese | 35% |
| Bengali | 60% |

Japanese retrieval is a material weakness. Bengali retrieval also needs improvement.

A separate IBM Granite multilingual model run reported 85% English, 70% Japanese and 45% Bengali on its own offline synthetic test. It is a different model/test run and must not be directly compared as though it were an A/B test on identical production data.

Both result sets are dense-retrieval synthetic metrics, not live user-answer accuracy. Do not change the production embedding model or the 384D vector contract solely from these numbers. First freeze a versioned, independently adjudicated multilingual gold set and measure Recall@k, MRR/nDCG, citation/evidence precision, answer faithfulness, unsupported-question abstention and p50/p95 latency by query/document language and retrieval fallback. Any model change requires a compatible re-embedding and rollback plan.

## 3. Capability and acceptance matrix

| Capability | Current classification | What remains unproven or blocked |
| --- | --- | --- |
| Next.js workspace and marketing site | Deployed | Independent browser/mobile usability and authenticated journey acceptance |
| FastAPI Core API | Deployed | Fresh public endpoint probe and representative authenticated smoke |
| PostgreSQL + pgvector and Redis | Connected in the deployed architecture; recent startup/readiness evidence exists | Full restore rehearsal and complete production operational acceptance |
| Document parsing, chunking and indexing | Implemented; 10 November vector coverage recorded above | New-upload to cited-answer acceptance under real provider conditions |
| Hybrid dense + lexical retrieval and RRF | Implemented | Measured end-to-end answer quality; current Japanese dense retrieval gap |
| Citation and grounding validation | Implemented | Adjudicated production false-accept/false-reject rate by language |
| Password and Google authentication | Code paths implemented | Complete independent two-account browser E2E, including expiry, reset, logout and recovery |
| API-side LiveKit credentials | Latest API startup auth probe PASS | Actual compatible voice-agent deployment, room join, bidirectional audio, STT/TTS, interruption, transcript persistence and reconnect E2E |
| Browser Agent | Production disabled | Isolated execution, SSRF/DNS/egress controls, durable approval and adversarial acceptance |
| Web Research | Tavily configured in production | Broad source-quality, current-news, Japanese/Bengali and outage acceptance; SearXNG remains limited/unverified |
| Private document/object storage durability | Partial implementation and provider probes exist | Full authenticated upload/finalize/read/restart/owner-isolation lifecycle and restore verification |
| Encrypted off-site backup and restore | Not verified | Independent database **and object** backup plus isolated restore rehearsal |
| Database RLS | Staged only; not enabled in production | Dedicated NOBYPASSRLS runtime role, transaction-scoped identity, worker/admin separation and PostgreSQL 16/18 cross-user acceptance |
| Company/organization tenancy | Not implemented as a complete product capability | Organization membership, roles, shared-workspace isolation, billing/quotas and company-level data boundaries |

**Important security distinction:** user-scoped authorization in application code is not the same as database-enforced RLS, and neither automatically provides company-level multi-tenancy. Aqlyra should not be marketed as an enterprise shared-company workspace platform until those boundaries are implemented and accepted.

The staged RLS PR #207 contains 17 policies for private parent/child tables, but its executable PostgreSQL acceptance test currently exercises only four representative tables (users, conversations, messages and memories). The remaining protected document, chunk, embedding, project, upload-intent, attachment and Study Abroad paths still need cross-user CRUD/worker/admin acceptance before rollout. The PR's own rollout note also warns that the transaction-local custom GUC `aqlyra.tenant_user_id` is writable by SQL running as the same role; arbitrary SQL or injection could spoof that identity or reset role context. This staged mechanism is defense-in-depth, **not a standalone isolation boundary against arbitrary SQL**. A trusted database identity binding and restricted query surface are prerequisites for commercial multi-tenant use.

## 4. Security and release governance

The active GitHub ruleset `aqlyra-main-production-gate` targets only `~DEFAULT_BRANCH` (currently `main`). It requires a pull request, one approval, last-push approval, resolved review threads, required checks and non-deletion/non-fast-forward protections. It does **not** target the active Vercel or Render release branches.

The current release workflows are still scoped to `main`; PR #213 proposes enabling CI triggers for `release/**`, but it also contains a substantial artifact-storage refactor. Separate and review the workflow-trigger/branch-gate changes from the storage implementation before requiring release-branch status contexts. Otherwise a ruleset could block all release PRs because its required checks are not emitted for those branches.

The connected GitHub integration could read the ruleset, but it could not read branch-protection details through the branch-protection endpoint or administer rulesets. A repository administrator must add a separate active ruleset for the exact frontend and backend release branch names (or a carefully scoped release pattern). Do not bypass protection.

The backend release PR **#36** remains open and is a large divergent release (517 commits / 449 changed files in the inspected PR metadata). It is not a routine documentation merge and must not be merged wholesale into `main` without a full integration review and required independent approval.

### Relevant open work

| PR | Purpose | Review disposition |
| --- | --- | --- |
| #207 | Staged fail-closed tenant RLS | Keep staged only. Never run its SQL directly on production before the runtime-role and identity-context prerequisites pass. |
| #213 | Release workflow and security gate changes, plus artifact/storage code | Mixed scope; the PR branch is behind/diverged from the live Core release. Rebase/review by file and complete release acceptance before considering merge. |
| #216 | Multipart ingress cap and atomic document-processing claim | Exact previously inspected head passed 8 checks, but the branch was one commit behind the deployed Core head; revalidate after rebase. |
| #217 | Revoke voice jobs on auth-epoch change | Requires compatible API and worker revisions deployed together. Exact previously inspected head passed 8 checks; revalidate integration. |
| #218 + #219 | Refresh-session rotation and BFF HttpOnly cookie persistence | Coordinated backend/frontend release. Apply and verify additive migration on staging first; do not deploy one side alone. Previously inspected heads passed their listed checks. |
| #220 | Collision-safe LiveKit state tempfile | A test-discovery indentation defect was fixed in commit `ea52f8c3a402c4d3870510d90476392eb53711c0`. After the test-discovery fix, all 7/7 checks passed on exact head `ea52f8c3a402c4d3870510d90476392eb53711c0`, including PostgreSQL 16 and 18. |
| #221 | Tenant RLS and durable-storage rollout plan | Documentation only; useful as a rollout checklist, not proof that the listed capabilities are live. |

Green checks on an earlier pull-request head do not prove that a newer integration result is green. Re-run and inspect exact-head checks after updating each branch.

## 5. Safe remediation order

1. **Operational visibility:** configure Render liveness paths as listed above; add an external uptime/alert probe and record cold-start, warm-start and dependency-failure behavior. Do not change service plans or production credentials without a separate decision.
2. **API/RAG acceptance:** run authenticated, non-sensitive test-account flows for login, upload, indexing, semantic and lexical retrieval, citations, unsupported-question refusal, memory and restart recovery. Record exact request, model, source revision and latency without logging private content.
3. **Multilingual quality:** establish the frozen gold set and baseline metrics before changing embedding model, chunking or ranking. Japanese is the first retrieval-quality gap to address.
4. **Session safety:** stage #218 and #219 as a coordinated migration/API/BFF release, including backup, legacy-cookie compatibility, concurrent refresh, replay, logout and reset tests.
5. **Voice:** reconcile the production LiveKit host with the CLI-selected project before creating/deploying an agent. Deploy the worker only to the verified production project, with a compatible API revision, then test a real signed-in call. Keep voice unavailable until acceptance.
6. **Tenant isolation:** implement and test the NOBYPASSRLS role, verified transaction-local identity and separate worker/admin credentials in staging. Only then plan a reversible production cutover.
7. **Storage and recovery:** prove upload/finalize/read/delete ownership, persistence after restart, checksums and cross-user denial; then perform encrypted off-site database and object restore. Never delete existing objects as part of a test.
8. **Governance:** add release-branch protection, rebase each security PR on the current release head and merge only after exact-head checks, review and operational acceptance.

## 6. Review actions taken

- Corrected the test-discovery indentation defect in PR #220 and committed `ea52f8c3a402c4d3870510d90476392eb53711c0`.
- Reconciled the 2 November LiveKit missing-credentials incident note with the 22 November API startup auth-probe PASS, while keeping actual call acceptance BLOCKED.
- No pull request was merged; no release branch was force-updated; no production deployment, database migration, RLS activation, storage cutover, data deletion or secret change was performed.
