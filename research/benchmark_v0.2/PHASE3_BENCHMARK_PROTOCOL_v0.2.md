# Aqlyra Phase 3 — Research Benchmark Protocol v0.2

Status: development protocol; not a final paper benchmark.
Main roadmap: Phase 3 — Research Benchmark & Dataset.

## 1. Research purpose

The benchmark measures retrieval behavior when a corpus contains a controlled fraction of documents/chunks that are lexically searchable but lack an embedding compatible with the active dense retriever. The primary system under study is Aqlyra's current hybrid BM25 + dense + RRF pipeline.

This protocol does NOT assume novelty. Prior work already establishes that missing embeddings can affect retrieval/evaluation, that partial embedding migration can reduce RAG performance, and that filtered vector search has recall/latency trade-offs. The benchmark therefore isolates the narrower engineering condition of incomplete dense coverage inside a hybrid fusion pipeline and tests whether the current fusion implementation remains robust when lexical candidates cannot receive semantic scores.

## 2. Prior-art-informed controls

The benchmark explicitly controls for confounds identified in prior literature:

- BEIR-style heterogeneous retrieval evaluation: retain query/document/qrels separation and report dataset-level results rather than only pooled averages.
- LoTTE/BRIGHT-style realistic and long-tail queries: include natural user queries in the external track; do not rely only on synthetic exact identifiers.
- DAPR: preserve document/passages separately and include some long-document / context-dependent queries.
- RRF: use the published reciprocal-rank formulation as the standard fusion baseline; do not present RRF itself as a contribution.
- Filtered vector search (ACORN/FVS/RACORN): keep metadata selectivity separate from embedding availability so a coverage mask is not mistaken for a normal metadata filter.
- Missing-embedding work: test both random and relevance-correlated missingness, because random coverage alone can hide the effect of which items lose embeddings.
- Partial migration work: report a dense-only migration baseline separately and avoid claiming that partial coverage effects are new in isolation.

## 3. Benchmark tiers

### Tier A — Controlled diagnostic
Purpose: verify causal behavior in a fully controlled environment.

- 48 source documents.
- 240 queries (5 query templates per source).
- Query types: lexical-anchor, paraphrase, entity+attribute, multi-hop, distractor.
- 7 coverage levels: 1.00, 0.90, 0.75, 0.50, 0.25, 0.10, 0.00.
- 10 deterministic masking seeds.
- Masking patterns: random, relevant-target, relevant-preserving.
- No exact query string copied verbatim into target evidence except in a dedicated lexical-anchor subset.

### Tier B — External natural-language retrieval
Initial development datasets:

- SciFact test
- NFCorpus test
- FiQA-2018 test

These are selected because BEIR provides diverse domains and qrels, while keeping the first development corpus manageable. Final selection can expand to LoTTE/BRIGHT after the first implementation is stable.

For development, use a fixed seed to select a documented subset. For the paper run, use the complete declared test split for each chosen dataset unless resource constraints are explicitly documented.

### Tier C — Aqlyra scope-aware stress test
Purpose: test whether user-scope filtering interacts with incomplete dense coverage.

- At least 4 users/tenants per experimental batch.
- Relevant and distractor documents distributed across authorized and unauthorized scopes.
- Unauthorized documents must remain excluded in every condition.
- Coverage is applied only within the authorized eligible set.
- Security exposure rate is a hard invariant, not an optimization target.

## 4. Experimental conditions

For every query, hold query text, corpus, qrels, user scope, embedding model, chunking, top-k, and evaluation code constant.

Primary retrieval conditions:

1. BM25 only.
2. Dense only.
3. Aqlyra current hybrid (BM25 + dense + current semantic-score eligibility behavior).
4. Research union-RRF comparator: preserve lexical candidates in fusion without requiring a compatible semantic score for lexical-only items.

Optional later condition:
5. Coverage-aware fallback/gating policy developed only after the baseline characterization is complete.

## 5. Coverage masks

Coverage rate is defined over eligible retrieval units:

AEC = compatible_embedding_units / eligible_units

Masking policies:

- RANDOM: sample units uniformly at the requested coverage.
- RELEVANCE-DEPLETED: preferentially remove embeddings from units judged relevant to the query. This is an adversarial stress test, not a naturally observed prevalence estimate.
- RELEVANCE-PRESERVING: preferentially retain relevant units while masking non-relevant units. This is a control for denominator-only effects.

The final paper must report exactly which masking policy generated each result.

## 6. Gold judgments

For external datasets, use published qrels. For Tier A/C, create gold relevance judgments before retrieval experiments and version them separately from system outputs.

Every benchmark record should retain:

- dataset_id
- document_id
- query_id
- document_version
- relevance_grade
- source_unit_id when applicable
- scope_id
- coverage_seed
- coverage_policy
- embedding_provider
- embedding_model
- embedding_dimension

## 7. Primary metrics

Retrieval:

- Recall@1, @5, @10
- MRR@10
- nDCG@10
- relevant-item retention under coverage
- rank displacement relative to full-coverage baseline

Coverage diagnostics:

- dense recall vs AEC
- current-hybrid recall vs AEC
- union-RRF recall vs AEC
- relative retention = metric(AEC) / metric(1.0)
- gap between current hybrid and union comparator

Scope/security:

- unauthorized retrieval count
- unauthorized retrieval rate

Latency is recorded but is secondary until the retrieval correctness implementation is stable.

## 8. Statistical plan (for Phase 7; schema fixed here)

Observations are paired by query_id whenever the same query is evaluated under multiple coverage conditions.

Do not treat coverage points or masking seeds as independent samples of users/documents.

For paired binary outcomes use McNemar-style comparisons where applicable. For continuous paired metrics, inspect distributions first and choose an appropriate paired test. Report effect sizes and confidence intervals, and control the family-wise or false-discovery error when multiple hypotheses are tested.

No p-value from the pilot is a novelty claim.

## 9. Reproducibility requirements

Record:

- Git commit
- benchmark version
- dataset source and checksum
- query/document/qrels counts
- embedding model and exact revision
- embedding dimension
- retrieval top-k and candidate multiplier
- RRF constant and weights
- masking seed and policy
- runtime environment
- raw run files
- metric outputs

## 10. Decision gates

Phase 3 is complete only when:

1. Benchmark datasets are reproducibly downloaded and checksummed.
2. Query/document/qrels schema is frozen.
3. Coverage masks are deterministic from stored seeds.
4. Relevance judgments are frozen and separated from outputs.
5. At least two natural-language external datasets run end-to-end.
6. Current Aqlyra hybrid can be evaluated without modifying production behavior.
7. Security invariants are verified on the scope-aware track.

Only after these gates should Phase 4 (Evaluation Framework) be considered complete.
