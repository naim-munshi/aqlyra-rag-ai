# Aqlyra Phase 1 — verified portfolio engineering evidence

**Assessment date:** 10 November 2026. This is a release acceptance snapshot, not a security certificate. The detailed design histories in earlier documents retain their original dates. **Do not delete or silently overwrite private user records or old cloud snapshots to improve a metric.**

## What can be demonstrated honestly

| Capability | Verified evidence | Interpretation |
| --- | --- | --- |
| Deployed backend | Render Free `release/core-without-study-abroad-20261027`; after hardening deploy `d7e98912`, HTTP 200 health/readiness, database and Redis ready | Public engineering beta, not an uptime SLA |
| Deployed frontend | Vercel `fix/center-empty-chat-composer-20261102`, production READY; public login with Google sign-in control; `/demo` clearly scripted | Real Google/password credential success and microphone use unverified |
| Dense indexing | Production Neon read-only count: **1,035 / 1,035 eligible current 384D vectors**, zero missing, zero quarantined answer-key vectors | Completeness of eligible vectors, **not** recall, precision or hallucination |
| Real Granite offline | [20-query real-model original run](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42760735012): English synthetic H@1 0.90, H@3 1.0, MRR@5 0.933 | Actual IBM Granite weights, **not** current production encoder |
| Real Granite multilingual offline | [60-query run](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42772861697): H@1 English **0.85**, Japanese **0.70**, Bengali **0.45** | Same ten synthetic English-source documents, 30 chunks; author-translated questions; repeated English scores differ (0.90 vs 0.85) across CI runs, so not a deterministic quality claim |
| Actual Aqlyra 384D static encoder offline | [512 MiB ONNX model run](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42775027087): H@1 English **0.70**, Japanese **0.35**, Bengali **0.60**; 60 labeled queries | Real production-weight model, **offline dense cosine only**, not live hybrid ranking. Japanese is a priority weakness. Immutable HF weight+tokenizer revision tracked in [PR #182](https://github.com/naim-munshi/aqlyra-rag-ai/pull/182) |
| Synthetic two-user HTTP acceptance | [PR #181](https://github.com/naim-munshi/aqlyra-rag-ai/pull/181) CI: `EPHEMERAL_E2E=PASS`; two independent synthetic users, real FastAPI HTTP + Postgres/pgvector, document upload/read, owner-ACL, cross-tenant refusal, RAG citations | Genuine HTTP integration, deterministic inference and local test accounts. **Not** live Google OAuth, actual provider or public SaaS pentest |
| Bounded concurrency | Existing CI 10–100 synthetic-chat load + 512 MiB Render Free resource envelope | Synthetic only; no proof of 100 simultaneous authenticated production users |
| Restore + OCR | [Disposable full database/uploads restore rehearsal](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42764481022): real scanned PDF OCR PASS, archive/hash verification PASS, local PostgreSQL and uploads restoration PASS | Real local disposable workflow; **not** Neon + private S3 off-host restore |
| Public API security | Recent low-impact GETs: document, conversation, memory, admin account APIs returned unauthenticated 401; backend/Next.js CSRF/SAST/dependency CI | No tested anonymous leak; **not** comprehensive penetration testing |

## Acceptance blockers — don't call enterprise production certified

1. **Real login:** Perform authorized successful Google OAuth and email/password verification, refresh, password reset, logout in actual Vercel/Render deployment; assert HttpOnly/no-store, owner separation and session revocation. Current anonymous BFF `/api/auth/me` returned 401; login UI and Google button rendered, but a real authenticated login was not executed.
2. **Real voice:** Browser microphone + LiveKit token/RTC + Railway worker + multilingual turn taking, end call/mic release; staging deployment may be healthy but cannot certify a real conversation without owner-approved microphone/session.
3. **Cloud disaster recovery:** Production Neon has a retained manual snapshot from **28 October** but **no automatic snapshot schedule**, and a new snapshot was refused due snapshot quota. No existing snapshot was deleted. Establish paid/allowed off-host backup and verify private cloud object restore in isolated staging; handle encryption, retention and least privilege.
4. **Failed files:** One legacy private PDF has `DocumentParsingError`; one legacy PNG has old Hugging Face embedding failure. Parser safety and owner-scoped image OCR retry have been implemented ([PR #178](https://github.com/naim-munshi/aqlyra-rag-ai/pull/178)); actual failed source bytes were **not** opened, deleted or automatically retried in production. Reprocess only after verified backup and owner-verified source availability.
5. **Production model & generation accuracy:** Actual production static encoder Japanese H@1 0.35 on this synthetic cross-language set; reranking, real-world retrieval and answer correctness/refusal need a separate independent representative dataset. Do not switch vector models under existing vector IDs, or include answer-key files in indexing.
6. **Protected main:** Backend release is hundreds of commits ahead of protected `main`; Vercel frontend lives on a different branch, and both contain different feature scopes. Existing [core integration PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36) needs independent human approval, dependency/security checks and release-scope review. Never bypass branch protection or blanket-merge divergent branches just to close a task.
7. **Production reliability:** Render Free cold-start, Groq 429 quota, memory limits, local artifact writes disabled/ephemeral test-only and no committed off-host recovery SLA. Bounded 429 cooldown cannot buy provider credits. Staging and outage testing remain needed.

## Release operations and source-of-truth rules

- **Backend release:** `release/core-without-study-abroad-20261027`. Roll out only after all GitHub checks on the exact **merged commit** pass; Render autoDeploy is disabled. Verify new Render commit ID, live health/readiness, read-only vector count and error logs before completion.
- **Frontend release:** `fix/center-empty-chat-composer-20261102`, not `main`; document-only merges on this branch do not prove a Vercel production deployment. Verify actual Vercel deployment metadata by commit.
- **Voice staging:** Railway `fix/voice-realtime-first-20261102`; successful staging worker deploy does not prove end-to-end microphone/RTC.
- **Do not treat scripted `/demo` as live inference.** Showcase the real deployed service separately with availability caveats.
- **Document the limitations with the benchmarks.** Do not use "enterprise-grade certified", "100% answer accuracy", "all production flows tested" or "fully finished" without the missing acceptance evidence.

## Minimum next evidence for Phase 1 release

For portfolio-readiness, independently verify and record (a) protected release head / CI / deployed SHA; (b) a successful and a failed actual account login with permission; (c) a real Bengali/Japanese/English RAG query set and citations under a test account; (d) voice mic call on real browser or explicitly mark unavailable; (e) cloud DR test using disposable copies; (f) 2-user permission-denied/role checks; and (g) artifact storage caveats, rollback plan and cost limits. No invented metrics.
