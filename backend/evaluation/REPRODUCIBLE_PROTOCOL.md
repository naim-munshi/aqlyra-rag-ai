# RAG Evaluation Protocol — evidence-first, not a production claim

## Audited scope (2026-11-08)

- Dataset: `backend/evaluation/retrieval_cases.json` has **20 labeled synthetic queries** over **10 synthetic corpus documents**, about **70 generated chunks** in the checked baseline. Each case references a filename and an evidence marker; the runner resolves these to existing chunk IDs.
- Existing baseline: `BASELINE.md` uses **deterministic SHA-256 embeddings**; this is retrieval-plumbing evidence, not semantic quality.
- `app/retrieval/evaluation.py` implements binary-relevance Hit Rate@K, Recall@K, reciprocal rank / MRR and nDCG@K; this change adds **Precision@K** (relevant unique chunks in top K divided by K) and macro mean Precision@K.
- Backend tests use fake providers or a synthetic database unless a real provider and exact model are explicitly recorded. Do not equate those tests with semantic accuracy.
- LLM reranker and query rewriter are feature-gated; historical Groq-assisted results in `BASELINE.md` are exploratory, not controlled reproduced production outcomes.

## Reproducible retrieval experiment

**Preflight:** use an isolated Postgres/pgvector database containing *only* the versioned synthetic corpus. Record Git SHA, database version, chunking configuration, embedding provider/model/dimension, source-file checksums, top K, candidate depth, feature flags, prompts, model snapshot and timestamps. Preserve owner/document scope. Never use live private data.

Use the **same queries, relevance labels and candidate depth** for each ablation:

| Variant | Required retrieval operation | Existing integration | Quality claim |
|---|---|---|---|
| Dense | true 384D embeddings + pgvector | `search_similar_chunks` | Blocked until real semantic provider run |
| Lexical | PostgreSQL FTS / bounded Unicode fallback | `search_lexical_chunks` | Measure independently |
| Hybrid | Dense + lexical RRF | `search_hybrid_chunks` | Blocked until real semantic provider run |
| Hybrid + reranking | RRF then reranker | `search_reranked_chunks` | Requires real provider run |
| Hybrid + query rewriting | Rewrite *retrieval* query before RRF | `_rewrite_retrieval_query` | Requires real provider run |
| Hybrid + rewriting + reranking | Both feature-gated steps | `_retrieve_rag_hits` | Requires real provider run |

**Important:** These implementation entry points are not proof that all six variants have been executed with real embeddings. Baseline and reranking tests mainly use deterministic embeddings or mocks. For an apples-to-apples study, run each variant on the same snapshot, same owner-scoped chunk IDs and identical K values (e.g., 1, 3, 5, 8). Disable RAG provider fallback when measuring strict dense quality; **record provider errors separately** instead of silently counting a lexical-only result as dense.

## Retrieval metrics (per query and macro average)

- Hit Rate@K = 1 if any labeled relevant unique chunk is in top K, else 0.
- Recall@K = number of relevant unique chunks retrieved / number of labeled relevant chunks.
- Precision@K = number of relevant unique chunks retrieved / K; absent ranking slots contribute zero.
- Reciprocal Rank = 1 / rank of first relevant chunk, or zero. MRR = macro mean RR.
- nDCG@K = binary DCG / ideal DCG; compute with deduplicated ranked chunk IDs.
- Latency: report p50/p95 of query embedding, lexical DB search, vector DB search, reranking and total retrieval **separately**; include warm/cold starts.
- Repeat complete rounds at least three times; report per-variant variance and errors (timeouts, HTTP 429, failure/fallback counts). Avoid means that hide 429 failures.

## Grounded-answer experiment (separate from retrieval)

For each answer use manually adjudicated evidence-level labels including answerable and unanswerable questions. Measure: (1) cited-source identifiers that actually belong to retrieved owner-scoped evidence, (2) claim-level supported/unsupported citations reviewed against text, (3) grounded answer accuracy, (4) correct refusals for unanswerable questions and (5) inappropriate refusals for answerable questions. Record end-to-end p50/p95, number of Groq/embedding calls and token counts with cost estimates.

Citation **syntax validation** and an LLM verifier are safety controls, but neither alone proves factual grounding. A correct `[S1]` reference can support a false claim; manual labeling is required to report accuracy.

## What remains unverified

No real-provider semantic evaluation result, six-way ablation table, grounded-answer accuracy percentage, end-to-end latency benchmark or real Groq quota reliability is asserted here. Require dedicated staging credentials, explicit expense budget, independent dataset and repeated executed runs before entering any values into a portfolio report.
