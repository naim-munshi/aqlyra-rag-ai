# Aqlyra Partial Compatible-Embedding Coverage Experiment v0.1

Status: pilot design; not yet paper-ready.

## 1. Experimental question

What happens to hybrid retrieval when the underlying authorized corpus is fully present but only a fraction of its chunks have compatible dense embeddings?

## 2. Oracle setup

Start from one fixed corpus in which every eligible chunk has:

- identical text;
- stable chunk ID;
- stable authorization labels/ownership;
- one compatible embedding record;
- complete lexical index coverage.

The oracle corpus is the reference truth for coverage interventions.

## 3. Coverage intervention

For each coverage level `c`, mask compatible dense embeddings for a controlled subset of **authorized** chunks while leaving all text and authorization metadata unchanged.

Recommended levels:

`1.00, 0.90, 0.75, 0.50, 0.25, 0.10, 0.00`

Use at least 10 independently seeded masks for the main pilot if the corpus size permits. Keep lexical indexing complete at every level.

Define:

`AEC = compatible_authorized_chunks / total_authorized_chunks`

where AEC = Authorized Embedding Coverage.

Also record global coverage separately so tenant-scoped effects are not hidden by the aggregate number.

## 4. Retrieval systems

### R0 — Lexical only
BM25/lexical retrieval over the complete text corpus.

### R1 — Dense only
Dense retrieval over only the currently compatible embedding subset.

### R2 — Current Aqlyra hybrid
Current lexical+dense implementation and its existing compatibility behavior.

### R3 — Union-RRF / coverage-aware fusion
Allow a lexical candidate to remain eligible even when no compatible dense embedding exists. Such an item contributes only its lexical-side rank/signal.

This is a baseline intervention, not a novelty claim.

### R4 — Oracle hybrid
Full compatible dense coverage (`AEC=1.00`) under the same query/configuration. This isolates the effect of missing coverage from other hybrid behavior.

## 5. Query strata

Use separate query sets for:

- exact identifiers / rare tokens;
- lexical paraphrase;
- semantic paraphrase;
- mixed lexical + semantic queries;
- multi-evidence questions where several units are required.

Keep the same canonical query across every coverage condition.

## 6. Primary retrieval metrics

- Recall@1, Recall@5, Recall@10
- MRR
- nDCG@10 when graded relevance is available
- Gold-evidence-unit recall@k
- Relevant lexical-only survival rate
- Relevant-candidate drop rate
- unauthorized retrieval count (must remain zero)

## 7. Rank-stability metrics

For each query compare each degraded condition against the oracle:

- overlap@k
- rank displacement of relevant units
- Kendall-style rank correlation when the item sets permit it
- probability that a gold unit falls below the final top-k because of coverage

Do not compare ranks across different candidate universes without explicitly reporting the universe change.

## 8. Failure accounting

Each failed query receives one primary mechanism:

- `lexical_miss`
- `dense_miss`
- `dense_coverage_miss`
- `fusion_displacement`
- `context_cutoff`
- `authorization_exclusion`
- `evaluation_ambiguity`

A coverage failure must not be counted as dense semantic-model failure.

## 9. Answer-level phase

Only after retrieval effects are established, select a subset of questions and run the generator.

Compare:

- current hybrid
- union/coverage-aware hybrid
- oracle hybrid

Measure:

- answer correctness
- supported-claim fraction
- unsupported-claim rate
- citation support
- abstention correctness

The main causal interpretation should remain retrieval-level unless the answer-level effect is independently demonstrated.

## 10. Authorization controls

Create at least two authorized scopes with different AEC values but identical question distributions.

Also include unauthorized distractor chunks containing the same target terms. Verify:

- unauthorized retrieval count = 0;
- no coverage-aware intervention can bypass user/document scope;
- AEC is calculated only within the authorized population.

## 11. Main ablations

A1. Coverage level.
A2. Masking random seed.
A3. Query type.
A4. Authorized-scope size.
A5. Top-k.
A6. Candidate pool depth.
A7. Current Aqlyra fusion vs union-RRF.

## 12. Statistical plan

Primary paired unit: the same query under the same authorization scope.

For binary outcomes, use a paired method such as McNemar's test where appropriate.

For continuous rank metrics, use an assumption-appropriate paired analysis and report effect sizes and confidence intervals.

The main experiment should pre-specify primary outcomes and avoid uncorrected multiple-testing claims.

## 13. Reproducibility

Persist for every run:

- benchmark version/hash;
- corpus version/hash;
- query version/hash;
- mask seed;
- coverage level;
- active embedding provider/model/dimension;
- retrieval configuration;
- candidate depth/top-k;
- authorization scope hash;
- git commit;
- raw ranked results;
- metric outputs.

Never mutate the oracle benchmark in place.
