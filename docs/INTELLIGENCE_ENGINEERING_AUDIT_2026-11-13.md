# Aqlyra — Engineering & Intelligence Audit
**Date:** 2026-11-13 (JST)  
**Method:** repository-wide tracked-file tree, high-value source-path review, PR history, GitHub Actions execution results, and Vercel deployment metadata. **No production database queries, secret disclosure, paid model calls, penetration tests or end-user microphone tests were performed.**

## Exact repository and release provenance

| Surface | Verified reference | Implication |
|---|---|---|
| Protected `main` | `6bd16d5f42bbb75989d7590ac7b33f7ae4e2f884` | Historical pre-production snapshot, not the active frontend |
| Core release candidate (PR #36) | `release/core-without-study-abroad-20261027@14cf64f7` | Has web research, safe calculator, richer RAG and memory fallbacks, staged study-related modules; does not equal `main` |
| Vercel frontend production | `fix/center-empty-chat-composer-20261102@d149b088`; deployment `dpl_G8QbgeymFJSEfKpY736npn8Bv9Bo`, READY | Changes merged only to `main` will not automatically update this live frontend |
| Earlier Core context fix | PR #95, `fix/groq-context-budget-20261102` | Tested bounded prompt history + social-turn policy; still separate from Core release head |
| LiveKit free-hosting work | PR #205 | Existing voice integration work; not a verified running agent |
| Open PRs | 48 (2026-11-13 inventory) | Branch stack, outdated bases and overlapping fixes need a reviewed integration matrix |

**Backend live release:** Branch PR metadata documents Core deployment, but the current Render service/commit, environment feature flags and external endpoints were **not independently verified in this audit**. Those require explicit access to the selected Render workspace and safe, authorized live probes. `READY` in Vercel means a frontend build deployed; it does not establish authenticated API/RAG correctness.

## Critical execution paths inspected

- **Converse:** `backend/app/services/chat_service.py`, `app/llms/registry.py`, `openai_provider.py`, `groq_provider.py`; normal chat history, response generation, SSE, document attachments, exact calculator and bounded public search routing.
- **Knowledge:** `services/rag_answer_service.py`, `services/hybrid_retrieval_service.py`, `retrieval_service.py`, `lexical_retrieval_service.py`, `knowledge_dense_coverage.py`, `rag/{context_builder,prompt_builder,citation_validator,grounding_verifier}.py`; user-scoped retrieval, hybrid fusion, gated reranking, evidence validation.
- **Memory:** `memory_retrieval_service.py`, `memory_lexical_retrieval.py`, `memory_extraction_service.py`; private contextual recall, embedding failures, consent and user-id-scoped access.
- **Research & tools:** `auto_web_research_service.py`, `smart_web_router.py`, `research_query_planner.py`, `browser_agent_service.py`; constrained research and browser behavior (not a general autonomous tool platform).
- **Security/ops:** `config/settings.py`, `docs/SECURITY_TESTING.md`, provider/error paths, GitHub CI, staging and production Docker configurations; status of security PRs #147/#149.
- **Real quality evidence:** `backend/evaluation/REPRODUCIBLE_PROTOCOL.md`, retrieval scripts and test inventory; tests on synthetic data must not be marketed as a production accuracy result.

This is a **critical-path audit**, not a claim that every line of all ~684 Core release files has received independent manual security review.

## Findings and concrete action

### P0: deployment truth & dependencies

1. **Release-branch drift, confirmed.** `main` and Vercel frontend diverge. Review source SHA + deployed environment per surface before shipping any feature. Preserve production DB and never merge 48 PRs indiscriminately.
2. **Historical `main` dependency audit FAIL, confirmed.** Scheduled Dependency Security Audit failed on 2026-10-26, 2026-11-02 and 2026-11-09 on `main@6bd16d5f`. Core PR #36's 2026-11-11 exact-head Dependency Security Audit passed. The current `main` pin set must be reconciled using reviewed security PRs #147/#149 before `main` becomes a release target. This does not establish a live exploit.
3. **Real environment is only partially verified.** Vercel production metadata is observed; current Render backend environment configuration and real voice agent dispatch are not verified. Do not claim end-to-end health or concurrency guarantees from CI alone.

### P1: answer quality & latency

4. **Normal chat context had no explicit UTF-8 byte budget in the Core release.** Twenty stored recent messages and optional memories can consume model context and trigger latency/context failures. Existing PR #95 bounds prior context to 32 KiB while preserving the current user message, and skips provider calls for pure low-information greetings. This audit extends PR #95 to carry explicit `context_window` completeness markers so the model cannot mistake omitted older turns for recalled facts. Updated tests verify multilingual byte budgeting, missing-context markers and prompt contract. **These are code and unit-test improvements, not proof of new real-world LLM reasoning accuracy.**
5. **Model routing is still limited.** Core has configurable Groq/OpenAI provider adapters and a single configured chat model. The default output budget is 800 tokens; live `LLM_MODEL`, `LLM_REASONING_EFFORT`, provider quotas and actual response truncation have not been measured here. Do not silently turn on cost-bearing higher models; trial candidate routing behind an explicit flag only after live baseline.
6. **Real semantic coverage is not fully established.** The Core path contains tenant-scoped dense-vector coverage detection, lexical-only behavior and remote-provider recovery. Verify *current* document chunks vs embeddings in production, track 429/timeout rates and reindex missing chunks with backoff/idempotency. The fallback must be surfaced as lexical-only, never mislabelled dense.
7. **Expensive knowledge enhancements are gated.** `RAG_RERANKER_ENABLED`, `RAG_QUERY_REWRITE_ENABLED`, `RAG_GROUNDING_VERIFIER_ENABLED` default off in Core settings. Enabling without a real, controlled evidence-recall/citation/latency benchmark can worsen accuracy, cost and 429 rates. Keep the conservative defaults until individually validated.
8. **Memory has a retrieval reliability dependency.** Semantic memory is optional, and lexical fallback is implementation-defined by flags. Validate per-user retrieval relevance, stale-memory correction, cross-user isolation, actual provider quota and latency. Never return internal memory metadata as fact.

### P2: measurable intelligence and agent capabilities

9. **Tool use exists, but is bounded.** Arithmetic, current public web research and approval-gated same-host browser investigation are implemented in release code. This is not unrestricted tools/coding/OS execution. Add new tools via explicit schema, permissions, owner check, timeout, audit logs and human approval rather than a general unsafe executor.
10. **No scored production-grade intelligence evaluation yet.** The documented controlled baseline is 20 labelled synthetic retrieval questions, 10 synthetic documents (~70 chunks). The protocol explicitly does not claim a real-provider six-way ablation, grounded-answer accuracy, end-to-end p95, multilingual production fidelity or human win rate versus other assistants.

## Suggested implementation sequence (preserve working features)

1. **Release hygiene:** identify exact current Vercel/Render/LiveKit SHAs; review Core, Frontend, Voice and Study Abroad branch matrix, de-duplicate PR overlaps, enforce independent reviews and 11 required checks; do not bypass protections.
2. **Immediate stability:** integrate reviewed PR #95 context budget and social-turn policy into the actual active Core release through the permitted review path. Monitor Groq context rejection, 429, p95 and user-visible continuity.
3. **Semantic coverage:** compare *owner-scoped* ready chunks versus indexed vectors, add bounded retries and a safe rebuild queue, confirm lexical fallback and citation refusal with adversarial tests.
4. **Quality experiments:** baseline real Groq answer quality over English/Bangla/Japanese reasoning, multi-turn context, sourced factual search, Knowledge retrieval, negative/unsupported queries; sample multiple rounds and report uncertainty and per-token cost.
5. **Flagged upgrades:** test a verified higher-quality model and/or conditional model routing; separately ablate rewrite, rerank and grounded entailment. Reject changes that do not improve measured answer quality or regress response time/quotas.
6. **Production acceptance:** browser + authenticated E2E, two independent private accounts, live voice, third-party failure and restoration tests, no secret leakage, rollbacks ready.

## Minimum acceptance data before claims

- Exact code commit and deployment ID for each runtime.
- English, Bangla, Japanese and code-switching prompts with reference answers and independent human scoring.
- Retrieval Hit/Recall/MRR/nDCG/Precision@K on the same synthetic and separate real-labelled fixture, plus citation support/refusal accuracy.
- Normal answer p50/p95 latency, first-token latency, number of provider calls, HTTP 429 rate, timeouts and memory usage.
- Evidence that one tenant's context never reaches another tenant or public web providers.
- Never claim ChatGPT/Claude parity or unlimited users without head-to-head testing.

## Scope & change log

**This audit's code changes are confined to existing PR #95**: normal prompt explicitly distinguishes the actual `current_user_message` from JSON context, and returns `history_truncated` / `memories_truncated` booleans without truncating the current request. Added focused regression assertions. No schema migration, production provider switch, user data modification, GitHub protection bypass or deployment is part of this step.

Relevant links: [PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36), [PR #95](https://github.com/naim-munshi/aqlyra-rag-ai/pull/95), [PR #101](https://github.com/naim-munshi/aqlyra-rag-ai/pull/101), [PR #149](https://github.com/naim-munshi/aqlyra-rag-ai/pull/149), [PR #205](https://github.com/naim-munshi/aqlyra-rag-ai/pull/205).
