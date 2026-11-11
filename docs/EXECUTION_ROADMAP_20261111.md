# Aqlyra — Audited Execution Roadmap (11 November 2026)

**Purpose:** Complete the **existing** Aqlyra RAG AI portfolio release safely, then evolve the same product toward a permission-aware enterprise AI platform. This is a prioritized working plan, **not** a claim of production certification or a blanket code audit. Never rebuild from scratch, swap vector models under the same model ID, erase user data, merge divergent release branches without review, or publish private credentials.

**Sources of truth:** [Phase 1 evidence](PORTFOLIO_PHASE1_AUDIT_20261110.md), [RAG pipeline](RAG_PIPELINE.md), [security assessment](SECURITY_AUDIT_2026-11-08.md), [repository cleanup](REPOSITORY_CLEANUP_REVIEW_2026-11-08.md), actual source/tests on each deployment branch, GitHub Actions run conclusions, **and independently confirmed deployed SHA**. Historical reports are not a substitute for fresh production checks.

## 0. Verified baseline and recent changes

| Area | Verified evidence | Unverified / remaining |
| --- | --- | --- |
| Backend source | \`release/core-without-study-abroad-20261027\`; [PR #185](https://github.com/naim-munshi/aqlyra-rag-ai/pull/185) merged as \`4d8b799665a3bcd6aadb37fc526aa3874a190ed1\` after 8 green CI checks | Exact deployed Render commit **not checked in this review**; protected \`main\` differs |
| Frontend live | \`aqlyra-ai.vercel.app\` production Vercel READY at commit \`e1ff769ba6820c7a26e11c7e2cf42e9a115da94b\`; auth hardening [PR #184](https://github.com/naim-munshi/aqlyra-rag-ai/pull/184) merged | Real successful Google/password account flow, cookies, refresh and logout not E2E verified |
| Health check | Production homepage HTTP 200; \`/api/health\` initially HTTP 503, then HTTP 200 on a repeat GET on 11 Nov ~13:21–13:22 UTC | Intermittent upstream readiness root cause and uptime distribution not known; do not infer 24/7 stability from retry |
| Indexing | [10 Nov documented read-only evidence](PORTFOLIO_PHASE1_AUDIT_20261110.md): 1,035/1,035 eligible current-vector chunks; seven quarantined answer-key chunks excluded | Recheck live vector hash/version/count after deploy; this is not proof of answer quality |
| RAG code | Auth-scoped retrieval; 384D static multilingual vectors + lexical fallback + RRF, citations, grounding/refusal; Japanese→English rewrite opt-in [PR #187](https://github.com/naim-munshi/aqlyra-rag-ai/pull/187) | Real user-grounded EN/JA/BN retrieval and answer quality; translation and reranker disabled until A/B validation |
| RAG benchmark | Actual production-weight *offline synthetic dense* Hit@1: EN 0.70, JA 0.35, BN 0.60 on 20 questions per language | No validated live answer accuracy; Japanese is a measurable gap |
| Security | GitHub backend PostgreSQL 16/18, SAST, dependency audit, synthetic security suites; two-user synthetic HTTP acceptance | Authorized real-account isolation and penetration testing in isolated staging |
| Voice | LiveKit integration and Railway worker code | Real browser microphone→RTC→STT→AI→TTS→interrupt/end call with owner test account |
| Backup/recovery | Disposable local PostgreSQL/uploads restore passed; [PR #188](https://github.com/naim-munshi/aqlyra-rag-ai/pull/188) prepares encrypted off-site export (NOT operational) | Independent S3 bucket/approval/keys, actual encrypted export, isolated *cloud* restore, measured RPO/RTO |
| Protected main | \`main\` is a historical baseline; on 11 Nov core was 495 commits ahead of it prior to PR #185 | [PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36) still requires scope/CI/protection review; do not blanket merge |

## P0 — Portfolio release blockers, in execution order

### P0.1 Exact deployment reconciliation and recovery

**Read:** release heads, deployment metadata and CI, Vercel/Render logs and readiness sources, env **names only**, not values.

**Execute:** compare deployed commit SHAs to GitHub release heads; create a reviewed, reversible backend deploy candidate; keep Render auto-deploy policy and staged approval; after deployment prove \`/health\`, \`/readiness\`, frontend \`/api/health\`, DB/Redis checks, semantic model identification and vector coverage. Test Render Free cold start using **low-rate** probes (no DoS). If staging or prod is unhealthy, roll back to previous known-good deploy. Do not claim PR merge equals production deployment.

**PASS evidence:** release SHA, CI URL/status for exact SHA, deployed backend SHA and deployment ID, readiness response, health before/after warmup, request latency samples and nonsecret error summary. **Current status: pending Render workspace selection and live deployment verification**.

### P0.2 Authentication, session reliability and owner privacy

**Execute:** use two explicitly authorized disposable user accounts with no personal material. Verify registration+email verification, password and Google OAuth, OTP resend/rate limits, refresh after Render sleep, account/session revocation, password reset, logout, CSRF and secure HttpOnly/no-store cookies. Exercise owner A versus owner B for documents, chunks, citations, direct cloud-object read, conversations, memory, projects, artifact downloads and admin endpoints.

**PASS evidence:** HTTP/UI steps and sanitized request IDs, correct authenticated success and nonowner 403/404, token invalidation, no cross-tenant data, no credentials in logs. Existing synthetic acceptance and anonymous 401 tests do **not** pass this gate. Review production auth fixes without reverting #184/#167.

### P0.3 Private file recovery and durable storage

**Completed in source:** [PR #185](https://github.com/naim-munshi/aqlyra-rag-ai/pull/185) verifies available local original or owner+checksum+size-bound finalized cloud original **before** requeueing a failed Knowledge file. Tests include missing local source, invalid cloud binding, valid cloud owner and foreign user 404.

**Remaining:** verify the fix on the exact deployed backend; confirm actual source *bytes* still exist before any owner-approved retry. Never auto-requeue the known failed legacy PDF/PNG simply to make a dashboard green. If local ephemeral bytes have disappeared, tell the owner a fresh safe upload is necessary; do not fabricate a recovered original. Make user-facing failure states actionable, without revealing object keys or internal paths.

**PASS evidence:** one authorized PDF OCR upload→index→cite, one image OCR case, retry success with existing original, 409 with missing original, cross-user refusal, no duplicate index records, stable checksum.

### P0.4 Off-host disaster recovery

Keep the existing 28 October Neon manual snapshot; do not delete it. Review #188 line by line and test nonsecret contracts. Configure a separate least-privilege off-host bucket and an offline private age key **outside chat**, then perform one authorized encrypted DB+private-object export and an actual isolated restore to disposable infrastructure. The existing local restore test and a proposed/manual workflow do not certify this.

**PASS evidence:** source and destination independence, ciphertext hashes, exact object hashes and owner matching, PostgreSQL 18 restore+schema validity, one owner-only retrieval, observed restore duration/RPO/RTO, explicit secure retention and rotation process. **Current status: blocked on owner-controlled recovery infrastructure and approval**.

## P1 — Advanced RAG quality (after P0 privacy/reliability)

### P1.1 Reproducible ingestion and retrieval evaluation

Build/maintain a **separate, versioned, synthetic or licensed** evaluation corpus with at least 30 English, 30 Japanese and 30 Bengali *independently labeled* questions, including multilingual queries for English-source docs, exact IDs, numerical comparisons, negation, out-of-scope/refusal, scanned PDF/image, and intentionally conflicting/poisoned documents. Quarantine answer keys and prevent benchmark leakage.

Score per-language retrieval H@1/H@3/Recall@5/MRR/Precision@5 and end-to-end exact/support quality, refusal correctness and citation precision (with confidence intervals where meaningful). Compare **real deployed model**, not deterministic test embeddings. Preserve 384D schema, content-hash validity, tenant filters, and existing lexical fallback.

### P1.2 Controlled intelligence improvements

A/B, **OFF by default** until data support them:

- Japanese→English retrieval-only rewriting from #187, with quote/ID/number/negation preservation and original-language answer.
- Existing optional reranking and rewrite, with provider 429/timeout fallbacks; measure cost/latency as well as accuracy.
- HyDE or multi-query retrieval only if independently evaluated and ACL-safe; no speculative uncontrolled extra LLM traffic.
- Bounded multi-hop evidence for cross-document answers; require provenance for every factual claim and enforce refusal when evidence is missing.
- Better language-aware lexical tokenization and deduplication while keeping exact-match identifier behavior.
- Retrieval/generation observability: query ID, safe per-stage latency, retry and fallback reason, actual model/version, citation/grounding failures, without logging private file bodies.

**PASS evidence:** blind labeled A/B improvement, no measurable tenant-isolation regression, honest source citations, bounded p95 latency, provider error resilience, no invented percentage improvements.

## P1 — Real-time Voice and usability

Test on physical iOS and desktop with a consenting authorized account: connect, audio permission, Bengali/Japanese/English speaking, streaming, stop/interrupt (barge-in), reconnection after cold start, manual hang-up, microphone release, denial/error UX, and no recording leakage. Inspect Railway worker logs without exposing transcripts. Treat worker \`Online\` as insufficient proof of conversation. Preserve existing Voice architecture.

Study Abroad UX should allow either ordinary chat or guided navigation while using the **existing** Fit Engine, eligibility/gap calculations and official-source research. No duplicate parallel engine or unnecessary registration funnel. Require real source attribution and data retention/consent checks before launch claims.

## P2 — Portfolio/release engineering and future enterprise extension

- Record a **real, scripted-by-human walkthrough** separately from the explicitly non-inference \`/demo\`: two-user login, upload, cited Knowledge answer, no-evidence refusal, multilingual case, optional live voice if passed. Link reproducible CI, model provenance and limitations.
- Reconcile stale \`main\` only through scope review of core and frontend, dependency audits, reviewer approvals and protected checks. Do not turn \`main\` into a substitute production trigger without acceptance.
- Keep CI matrix for Python 3.13 + PG16/18, Next.js lint/type/build, security, real-model 512 MiB, staging smoke, accessibility/mobile tests and release guard.
- Enterprise Phase 2 (after Phase 1 passes): permission-aware Google Drive/other enterprise ingestion, connector change-data-capture, multi-source search, auditable policy-based tool actions, admin tenant billing/quotas and stronger isolation. Explicit consent, provider scopes, provenance and feature flags; **no replacement of current architecture**.

## Completion decision / gates

**Do not mark "fully complete"** until: (1) exact deployed release SHA matches audited code, (2) live authenticated account flows and two-user isolation pass, (3) public RAG PDF/image ingestion and source citations pass, (4) representative EN/JA/BN retrieval and grounded-answer scorecards exist, (5) voice on real mic is either accepted or explicitly unavailable, (6) actual independent cloud backup/restore passes, (7) dependency/security/CI and a reversible deployment runbook pass, (8) no known P0 data loss/security blocker remains.

**Operational constraints:** production data is immutable during validation unless the owner explicitly authorizes a narrowly described migration; no hidden API key exposure; no high-volume production testing; no auto-activation of browser automation or paid providers; no unaudited cloud backup runs. Every result must distinguish **implemented**, **CI verified**, **deployed**, **real-user verified**, and **blocked**.
