# Aqlyra — Verified production recovery and acceptance status

**Observation date:** 2026-11-02 JST. **Source of truth:** existing user-owned product, repository and connected Vercel, Render and Railway providers. Evidence is point-in-time; provider state may change.

> **Release verdict: BLOCKED for full production acceptance.** This is not a new application, not a migration, and not proof that synthetic tests or startup readiness constitute authenticated E2E acceptance.

## Existing deployment inventory (independently checked)

| System | Existing component | Observation and evidence | Gate |
| --- | --- | --- | --- |
| Official app | https://aqlyra-ai.vercel.app; Vercel project `aqlyra` | Production `dpl_CnwFJWRD2LRy7HcR1iso4Gha3hNr` previously checked READY, frontend real-LiveKit path | Live, mobile browser + signed-in E2E still unverified |
| Core API | Render `srv-dbgjt0ei0phs73akd8j0` (`aqlyra-api-free-launch`) | **Live** deployment `dep-dbjrsi6tlv9c73e42v00` at exact code commit `74f7a6d63e976aedfd6344afb08cdaeef9ad8cb0`; branch `release/core-without-study-abroad-20261027`. All 8 PR-associated workflows on this commit succeeded. | PASS deployment and config, not user E2E |
| Render voice configuration | Existing Core FastAPI | Older startup logs explicitly lacked `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`. After owner supplied values and same-code Render redeploy, startup at **2026-11-01T22:34:50Z** logged `voice_api_startup_ready=true`. The old missing-key warning did not appear in that startup event. | **PASS only for server-side configuration readiness** |
| Voice worker | Railway project `Aqlyra-Staging`, environment `staging`, only service `aqlyra-voice-worker` | Deployment `396a246d-a8fb-406b-82ad-3aba3926f499` SUCCESS; runtime `voice_worker_preflight=PASS`, `registered worker`; no network-verified dispatch job or audio trace. `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `REMOTE_SEMANTIC_TOKEN` are present as *variable names*, values withheld. | Worker registered; actual conversation BLOCKED pending user session |
| Semantic model worker | Render `srv-dbiq8fcs728c7380tlag` | Deployed worker commit `156bc48fea6c19f5755faede8431d4a4d0a43b38` LIVE. Production model `bekko-static-multilingual-int8-mrl384-v1` and **384-dimensional** schema remain authoritative. Historical Core HTTP 502; worker runtime logs show clean shutdown/startup cycles, **not** confirmed OOM. | P0 provider-backed success and cross-owner RAG E2E **not yet accepted** |
| Data and cache | Existing Neon PostgreSQL + pgvector, Redis | Unchanged by this recovery. Neon connected project enumeration did not work in this audit; no database query, migration, backup or restore was performed. | Backup/restore and isolation BLOCKED |
| Live Web | Existing Tavily primary, experimental SearXNG | Existing architecture unchanged; no provider-backed research accuracy or citation acceptance performed in this turn. | E2E BLOCKED |

## Security and reliability work completed as **drafts** (NOT production deployed)

1. [PR #95](https://github.com/naim-munshi/aqlyra-rag-ai/pull/95): Bounded old chat history/memory input context while preserving the complete current user message for normal/streaming Groq turns. Backend workflow previously verified PASS. Do not claim that provider context limits are solved until provider-backed tests.
2. [PR #96](https://github.com/naim-munshi/aqlyra-rag-ai/pull/96): Explicit non-cacheable LiveKit participant JWT origin responses (`Cache-Control: private, no-store`, `Pragma: no-cache`); backend PostgreSQL 16/18 workflow PASS.
3. [PR #97](https://github.com/naim-munshi/aqlyra-rag-ai/pull/97): Explicit no-store on all 7 Next.js voice session-token proxy paths, security regression and corrected LiveKit [owner recovery runbook](VOICE_FREE_TIER_SETUP.md); most recent exact-head 5/5 workflows PASS (including ARM64).
4. [PR #98](https://github.com/naim-munshi/aqlyra-rag-ai/pull/98): Strict 384-d semantic-vector type/finiteness validation, stable normalization for extreme finite vectors, addition of **binary NDCG@K** to existing retrieval evaluation and targeted regression tests. Latest exact-head CI must finish before review/acceptance.
5. [PR #90](https://github.com/naim-munshi/aqlyra-rag-ai/pull/90): Current deployed real-time frontend/worker release lineage; declared draft; do not wholesale merge into diverged Render Core.
6. [PRs #84–85](https://github.com/naim-munshi/aqlyra-rag-ai/pull/84): Safe Browser Agent backend/frontend companion candidates. Production unsafe execution remains OFF; no remote browser sandbox acceptance.
7. [PR #82](https://github.com/naim-munshi/aqlyra-rag-ai/pull/82): Durable generated-file storage candidate. Not verified for production data migration or multi-format persistence.

These changes are separate from the running Render Core commit. A green PR CI does **not** authorize protected `main` merge, branch replacement or production release.

## Observed risk and root-cause classification

| Priority | Defect | Evidence | Current mitigation or next test |
| --- | --- | --- | --- |
| P0 | Voice backend had empty LiveKit credentials | Repeated `voice_api_startup_ready=false` before 22:34 UTC; now true after owner configuration + same-code redeploy | Server configuration fixed. Must still prove API JWT uses *same LiveKit Cloud project* as named worker, then real audio |
| P0 | Historic intermittent remote embedding HTTP 502 | Previous Core 502 and observed semantic worker shutdown/startup; no proof of OOM | Existing bounded retry/circuit breaker deployed. Test authenticated vector embed and document/memory retrieval with exact model/dim; record provider trace and latency |
| P0/P1 | Groq oversized-history/429 degradation | Core commit handles errors; context budget PR #95 not live | Review PR #95, run exact-head independent checks and provider-backed normal/SSE tests |
| P1 | Malformed/overflowing remote vectors | Source inspection of `remote_semantic_provider.py` and `normalize_vector`; PR #98 pending CI | Never fabricate or silently accept bad vectors; no model swap |
| P1 | RAG quality missing NDCG | Existing retrieval evaluator exposes hit/recall/MRR but no NDCG | PR #98 adds metric. No measured production Recall@K, MRR, NDCG, citation support or multilingual benchmark yet |
| P0 | Comprehensive release security | Open [issue #34](https://github.com/naim-munshi/aqlyra-rag-ai/issues/34) | Protected-main enforcement, backups/restore, isolated Browser Agent egress and real two-user E2E remain gates |

## Strict next-release dependency order

1. **Voice E2E before claim of readiness:** Existing Render configuration is now true, but verify sign-in on official Vercel URL, authenticated voice status, actual room JWT mint, agent dispatch to the **registered** Railway worker, real iPhone and Android microphone → Deepgram STT → same `execute_chat_turn` RAG and tools → audible Cartesia TTS. Test English, বাংলা/Banglish, 日本語, spoken stop/barge-in, mute, reconnect, and two-user document/conversation isolation. No access to the user's physical mic was available here.
2. **Semantic provider acceptance:** Request the real worker with authorized test credentials without logging any key or private text; verify `384` and pinned model, actual vector normalization, existing user-owned docs, lexical degraded mode, 502 recovery, citations and cross-account denial.
3. **Safe code review:** Merge neither experimental Browser Agent nor schema-changing artifact storage. PRs #95–98 remain separate drafts, require exact-head CI, small diff review, staging and explicit authorized deployment to the current services.
4. **Production data protection:** Prior to migrations or storage cutover, verify non-production backup restore, stable JWT/object-signing key, owner isolation, document ingestion recovery, controlled rollback.
5. **Release acceptance:** Complete real authenticated two-account security tests, five office/PDF file creation+download+restart checks, Gmail OTP and OAuth, study-abroad official-source QA, mobile voice tests, actual RAG benchmarks and measured availability/latency/voice TTFA. Mark each PASS/FAIL/BLOCKED with timestamps and evidence. Update public README only after verification.

## Release policy

No duplicate frontend/API/AI brain/database; no secret disclosure; no unapproved production data writes/migrations; no fabricated benchmarks; no protected main merge; no unverified Browser Agent permissions. A successful service deployment, an API `ready=true` flag, a worker registration, and a synthetic CI pass are **four different facts**, none independently proves end-to-end human voice or RAG acceptance.

**Current deliverable:** verified configuration recovery, tested isolated source patches, updated operator runbook and this release status. **Overall Master Engineering Prompt definition of done is NOT yet met.**
