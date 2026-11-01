# Aqlyra: owner engineering directive and verified recovery baseline

**Last audited:** 2026-11-02 JST. **Project:** `naim-munshi/aqlyra-rag-ai`.  
**Authority:** owner-provided *MASTER ENGINEERING PROMPT — AQLYRA ADVANCED INTELLIGENCE & PRODUCTION RECOVERY* (2026-11-02). This file is a compact, durable implementation contract; it does not replace the full owner instructions. Revalidate every operational claim before deployment.

## Product invariants (mandatory)

1. **Evolve the existing product; never rebuild it.** Preserve user identities, documents, chat histories, JWT/OTP boundaries, owner-scoped search, PostgreSQL/pgvector, the existing 384-d embedding schema, Redis, private file architecture, migrations, history, protected `main`, and official production URL.
2. Maintain the current **Next.js/Vercel frontend, FastAPI/Render API, LiveKit/Railway voice worker, Neon PostgreSQL/pgvector, Redis, existing Groq provider, Tavily plus experimental SearXNG, and approved private object storage**. Do not create a second chatbot brain or duplicate service to conceal an integration failure.
3. **One authorized AI execution path:** existing `execute_chat_turn` and configured tool routing should serve text, voice, retrieval, memory, web research, math, documents, and file operations. Add capabilities to the current orchestrator rather than replacing working ones. Simple questions should avoid extra model/tool calls.
4. Don't claim capabilities based on UI, stubs, mock tests, registered workers, green builds, or source-code presence. Distinguish **implemented / deployed / real-provider verified / independent-user E2E accepted**.
5. Keep provider identity, vector model provenance and citations explicit. Never substitute deterministic vectors or an incompatible embedding model, disclose private document text to public search, expose LLM reasoning traces, fabricate evidence, or bypass authorization.
6. No protected-main merge, force push, deletion of user branches or production data, irreversible schema changes, object-store cutover, unreviewed keys, unsafe browser execution, or deployment of overlapping PRs without explicit release authorization and required checks.

## Audited operating baseline (not acceptance)

| Surface | Verified 2026-11-02 state | Follow-up |
| --- | --- | --- |
| GitHub | **55 open PRs, 52 draft**; many stacked on historical branch heads. `main` is behind both live release lines: Core ahead 294 and current Voice/UI branch ahead 415 commits. | Preserve all history; classify dependency/conflict, do not blindly squash everything or close PRs. |
| Official frontend | `https://aqlyra-ai.vercel.app`; Vercel deployment `dpl_CnwFJWRD2LRy7HcR1iso4Gha3hNr`, commit `38fa9e142a88aa4ad4f30664ef294cd1f9fd7d4c`, READY. | UI and production mobile experience need independent test. |
| Render Core API | `aqlyra-api-free-launch`, service `srv-dbgjt0ei0phs73akd8j0`, branch `release/core-without-study-abroad-20261027`, latest observed live commit `bd0c3160e8c39d7e69ddeab203a130ddcf9e9679`. | Do not replace this divergent Core branch with frontend branch wholesale. |
| Railway | `Aqlyra-Staging` single current Voice Worker, `aqlyra-voice-worker`, commit `38fa9e142...`, 1/1 replica Online and preflight/registration PASS. | This is NOT an authenticated microphone or agent-dispatch E2E PASS. |
| Voice blocking defect | Render startup log: `voice_api_startup_ready=false`, missing `LIVEKIT_API_KEY,LIVEKIT_API_SECRET`. | Configure **matching existing LiveKit project credentials on the same Render API**, via protected secret management; then validate room/token/agent dispatch and human audio. Never print the values. |
| Semantic embedding worker | `https://aqlyra-semantic-worker.onrender.com`, service `srv-dbiq8fcs728c7380tlag`; exact `bekko-static-multilingual-int8-mrl384-v1` ONNX model, **384 dims**, single CPU inference instance. Earlier real /v1/embed HTTP 200 and subsequent repeated 502 from Core requests. Render free instance ~0.15 CPU, 512 MB limit; OOM **not confirmed**. | P0 reliability. Existing client retried zero times; draft PR #93 adds bounded transient retry plus process-shared circuit. Validate exact-head CI and authenticated real provider before promotion. |
| Web | Tavily integrated, separate SearXNG Render service registered `srv-dbifcijbc2fs73faq3s0`. | SearXNG federation is not a private independent web index. Keep provider evidence/citations and privacy guards. |
| Security/release | Issue [#34](https://github.com/naim-munshi/aqlyra-rag-ai/issues/34) has unresolved independent security, backup, network-isolation, and multilingual E2E gates. | Do not infer branch protection from a CI workflow label. |
| Neon database | Existing schema is used by production. Neon plugin project enumeration was unavailable in this audit session. | DB schema/restore, migration readiness and auth isolation NOT independently verified here. Do not change production DB. |

**Important:** Backend and frontend branches have **diverged** (Core -> current UI: ahead 160/behind 39 as observed). A whole-branch merge or service swap could roll back production features. Inspect per-file diffs and use small compatibility backports.

## PR consolidation map — do not delete work

| Group | Related existing PRs | Required handling |
| --- | --- | --- |
| Core/live release | #36, #37, #58 | Compare live commits and integration requirements; #36 is the current Core ancestor. #58 is the frontend integration release line, not a drop-in backend replacement. |
| Voice | #40, #41, #83, #86, #89, #90 | Most recent #90 is running UI/Worker code. Older voice PRs contain security and language-turn fixes, some already integrated in the running line. Diff each against live, mark superseded only after proven; keep human voice E2E gate. |
| Semantic P0 | #8, #28, #42, #44, **#93** | The existing `remote_onnx` 384-d worker stays authoritative. #93 is current isolated retry/circuit candidate, **not automatically production ready**. |
| Browser Agent | #16, #20, #31, #84, #85 | Browser execution stays disabled in prod until signed approvals, DNS/egress sandboxing, SSRF, user isolation, prompt injection and real E2E pass. PR #84 backend and #85 frontend are related but separate. |
| Storage/files | #14, #27, #29, #49–53, #82 | Preserve private object-storage and legacy data. #82 contains durable artifact rollout work; require stable signing keys, backup/restore and five-format/cross-owner acceptance before enabling. |
| Knowledge/RAG | #54, #55, #56, plus currently deployed Core RAG | Do not create a second index; compare K1/K2 queue/OCR with current Core. Maintain citation provenance and identical retrieval/model contracts. |
| Web/research | #12, #19, #46–48, #84–85 | Preserve auto-search, citation/consent, Tavily fallback and cost controls; avoid duplicate tool windows or new engines. |
| Identity/security | #10, #11, #23–26, #28–35, #38, #43 | Verify exact changed-file patches against production; most are older stacked/integration candidates. No assumption of deployment. |
| Study Abroad | #22, #26, #37, #39 | Release independently from existing Core with migration/official-evidence review. |
| UI/documentation | #7, #9, #21, #45, #81 | Treat historical patches as candidates, not evidence of production bug still present. |

The older 55 open PRs contain **52 drafts**. Do not automatically close them or merge to `main`; classify each by actual deployed-file equivalence before any owner-approved cleanup.

## Dependency-aware engineering phases and acceptance

- **P0 · Ground truth and incidents (Phase 0–1):** Confirm provider configuration and exact live commits, inspect worker and API logs, fix repeated 502/503, ingestion failures and durable memory degradation. Observe true vector provenance and no cross-account disclosure. A 200 health response is not a real embedding request PASS.
- **P1 · Unified brain (Phase 2):** Keep existing `execute_chat_turn` and its memory/RAG/search router; build bounded structured tool selection, exact math, assistant answer verification, context-aware follow-ups, uncertainty and relevance. Do not add LLM calls for trivial intents. Tests: self-description vs founder identity, stop, follow-up, current facts, math, private PDF.
- **P2 · RAG quality (Phase 3):** Benchmark baseline Recall@K, NDCG, MRR, citation entailment, abstention, latency and cross-language recall before changing hybrid ranking, chunking or rerankers. No model/dimension substitution without compatible evaluated migration. Page-level citations, multilingual parsing, OCR, retries and user ownership are required.
- **P3 · Realtime voice (Phase 4):** Text and LiveKit worker use the **same** authorized chat/research/math brain; native multi-language STT/TTS, code-switching, endpointing/VAD, barge-in, cancellation, non-overlapping speech, natural pacing, connection/mic lifecycle. No mandatory language picker. Actual signed-in iOS/Android microphone and two-account E2E required; voice-worker registration alone never counts.
- **P4 · Research and agents (Phase 5):** Conditional search with current citations, multi-source verification, chronology checks, no private data transfer to public search. Browser actions require explicit approval, SSRF/DNS/egress protection, sandbox, bounded execution and audit trail.
- **P5 · Identity/files (Phase 6):** OTP-before-activation, OAuth, reset sign-in, JWT revocation, guest isolation, private document ownership, encrypted backups and restore rehearsal. Generate, download and validate PDF/DOCX/XLSX/PPTX/Markdown in normal chat with multilingual rendering and safe persistence.
- **P6 · SRE/performance (Phase 7):** Instrument provider errors, startup readiness, p50/p95/p99, TTFA, token costs, retry budgets, queue/restart persistence; measure, don't invent SLOs.
- **P7 · CI/release (Phase 8):** Small branches, regression/security and Compose tests, exact-head backend PG16/18/frontend/ARM64 checks, staged operator canary, explicit deploy target, runtime log confirmation and reversible rollback. Keep `main` protected.
- **P8 · Real acceptance and delivery (Phase 9–10):** Disposable user accounts, real private PDF and cross-user 404 tests, native voice/interruptions, provider-backed web search, five file formats, account lifecycle, data/backup restore; document outcomes as PASS/FAIL/BLOCKED and update README/runbooks/feature matrix.

## Definition of done

No open P0 incidents; measured semantic retrieval, grounded citations, relevant answers, safely authorized tools and files; natural bilingual/multilingual speech with real device audio acceptance; private user isolation, resilient storage and safe backups; exact-head release CI PASS; correct observed latency/cost metrics; and accurate production documentation. **Never use mocked tests or a successful deploy to claim any of these independently.**

## Operator continuation checklist

1. Read this directive, live Render/Railway/Vercel deployment identifiers, and issue #34; compare *live* SHA against the PR under review.
2. Pick the top unresolved P0 and examine **existing** implementation before writing code. Check overlapping PRs first.
3. Make bounded change, regression tests, exact-head CI. Prefer one existing service/branch rather than new resources.
4. If blocked by provider secrets, identity or live private accounts, record exact key **names only**; do independent safe work without guessing values.
5. Roll out only isolated, authorized targets; verify actual provider traffic and user behavior; publish precise status and remaining blockers.

This file is the **project-persistent engineering baseline** requested by the owner, not a claim that the ten phases are complete. Keep it updated with verified evidence, not dated guesses.


## Verified per-file PR collision sample (2026-11-02)

GitHub's complete changed-file lists reveal important nontrivial intersections. These counts are not semantic conflicts by themselves, but prohibit blind whole-branch merges:

| Candidates | Identical changed paths | Specific risk |
| --- | ---: | --- |
| #93 semantic P0 vs #90 running Voice/UI | **1** | Both change `backend/app/embeddings/remote_semantic_provider.py`. Must review against deployed Voice Worker and Core before backport; do not replace unrelated voice improvements. |
| #90 Voice/UI vs #89 voice language | **7** | Shared voice worker, TTS routing, model factories and tests. #90 is currently deployed and may already contain #89 behavior. |
| #90 Voice/UI vs #58 unified frontend | **7** | Shared Voice button, browser fallback, settings and chat service; source branches diverged. |
| #84 Browser Agent vs #85 browser UI | **2** | Shared frontend deployment workflow and browser workspace; pair release with review, not blind merge. |
| #82 durable storage vs #54 knowledge | **19** | Shared backend artifact API/storage, worker settings and CI. |
| #82 durable storage vs #56 OCR/knowledge | **19** | Same shared artifact and release files. |
| #93 semantic P0 vs #82 storage | **0** | No identical paths, but both are based on Core; still require backend and security acceptance. |

Any actual promotion must revalidate the exact head at that time. The metadata-only audit cannot establish which historic PR contents are already semantically deployed. PR closure/supersedence is **not authorized by this file**.
