# Aqlyra RAG quality, grounding and latency A/B protocol

**Date:** 2026-11-16. **Status:** Instrumented and CI-tested synthetic comparisons; no new production model is enabled.

## Audited facts

- The existing hybrid engine uses dense+lexical reciprocal-rank fusion.
- `RAG_RERANKER_ENABLED` is an existing feature flag and is **off by default**. Existing providers are `llm` or `identity`; a new cross-encoder is not needed until an independent holdout demonstrates uplift at acceptable latency and cost.
- The citation validator checks IDs, syntax and claim-block citations, **not truth**. The existing `LLMGroundingVerifier` checks entailment of cited sources and can trigger repair/refusal. Production startup requires grounding verification to be enabled, but a runtime flag does not prove verifier accuracy.
- Normal-chat SSE streams model deltas. Document-grounded responses need retrieval, full generation and claim validation; the normal conversation endpoint currently emits a full validated document answer as a **single delta**, and knowledge-mode SSE is not supported. Do **not** claim first-token streaming for grounded answers.
- The index uses pgvector HNSW on 384-dimensional embeddings. Its memory, index build, recall and disk footprint must be measured for the actual data volume; there is no hard 5–10 million chunk threshold.

## What this PR actually measures

1. `run_reranking_benchmark_once()` reuses the same labeled queries and candidate depth for vector, hybrid, and hybrid+reranker. New `stage_latency_ms` has p50/p95/max and sample count for query rewriting (when used), vector, hybrid, rerank, and combined hybrid+rerank. Measurements are sequential stage timings **not production p95 or end-user streaming TTFT**. The full reranker path must not be silently substituted by identity/fallback when claiming reranker quality.
2. CI runs a **synthetic** PostgreSQL 16, four-script baseline (Unicode fusion OFF) versus experimental (ON). It reports Hit@1, MRR@3, nDCG@3 and measured in-process p50/p95. It asserts that English/Banglish do not regress and that foreign-tenant content never appears. This tests lexical fusion, **not dedicated cross-encoder accuracy**.
3. Grounded-answer execution now logs numerical retrieval, context assembly, generation, citation validation, verifier and repair latency, including invocation counts and refusal outcome. No question, user ID, evidence or answer content goes into the new metric log. This measures the cost of holding an answer for verification; it does not create partial unsafe token streams.
4. The existing SSE endpoint logs **backend time to first emitted delta** in two distinct buckets: `normal_model_delta` vs `validated_full_answer`. The latter waits for document/web answer completion and must never be described as first *model* token. Both are server-side timings, **not browser network TTFT**.
5. `app.rag.grounding_evaluation.summarize_grounding_trials` scores manually adjudicated expected-support labels against real verifier verdicts by language. It counts unsafe false accepts, false rejects and unavailable/error verdicts separately, with provider latency percentiles. Synthetic unit tests validate the metric math only; **the current PR does not contain real Groq/NLI verdict accuracy measurements**.

## Independent quality acceptance before enabling rerank or changing streaming

- Reuse `backend/evaluation/retrieval_cases.json` and `retrieval_cases_cross_language.json`; score 20 existing English cases and each Japanese/Bengali translation **separately**, and add independently hand-reviewed Banglish and unanswerable cases. These are synthetic translations, so do not advertise results as user-traffic accuracy.
- For serious release evidence, create an independent labeled holdout (at least 20 per language, ideally 50+ each) with actual chunks and permission boundaries. Run 3+ rounds with the same tenant, snapshot, exact model revision, normalized input and candidate pool.
- Compare **vector**, **lexical**, **hybrid RRF**, **hybrid+current LLM reranker** and an optional *locally operated* cross-encoder in an isolated environment. Record errors and 429s in denominator, and track hit@1/5, recall@5, nDCG@5, MRR, hallucination/refusal rates, and p50/p95.
- A reranker is valuable only if it improves evidence ranking by language without reducing strict tenant isolation, breaching provider data-processing approvals, or causing unacceptable p95, cost and quota failures. The former `>90%` claim is **not a guaranteed outcome**.
- Manually adjudicate sentence-level grounding: supported, unsupported, contradicted, missing evidence, and unanswerable, including numbers, negations, Japanese and Bengali translations. Report verifier false-accept rate separately from correct refusals and latency. Requiring an LLM to say `SUPPORTED` is not itself proof.
- Measure real backend endpoint elapsed latency and SSE time-to-first-*validated* delta at client/network boundaries. Separate normal-chat TTFT from document-grounded answer completion. Do not enable speculative streaming of unverified facts.
- Measure HNSW footprint and filtered-query recall/latency under realistic tenant distributions before designing a different vector architecture.

## CI and operational checks

- Use the GitHub Backend Tests workflow on the PR head: PostgreSQL 16 & 18 plus isolated security checks. The PostgreSQL 16 job prints `AQLYRA_SYNTHETIC_MULTILINGUAL_LEXICAL_AB=` with aggregate metrics.
- Inspect numeric `rag_stage_latency_ms` entries in authorized backend logs; they contain no source/user text. Segment by deployed SHA and workload before comparing p95.
- Keep `RAG_RERANKER_ENABLED` and normal-chat/knowledge streaming contracts unchanged. Never send private chunks to an unapproved external reranking API just to improve a benchmark.
- Only deploy code after green exact-head CI. Do not claim live quality improvements from synthetic tests or change production RAG feature flags before independent evaluation.
