# Aqlyra Phase 3 — Research Benchmark Protocol v0.3

Status: development protocol; not a final paper benchmark.
Supersedes v0.2 for active benchmark construction while preserving v0.2 as
historical development record.

## 1. Research purpose

This benchmark evaluates retrieval behaviour under controlled incomplete
compatible dense-embedding coverage.

The primary intervention changes whether an eligible retrieval unit has an
embedding compatible with the active dense retriever.

The corpus, query set, authorization scope, retrieval configuration, and
evaluation procedure remain fixed within paired comparisons.

The benchmark does not assume novelty.

## 2. Primary research question

How does retrieval performance in a hybrid lexical+dense RAG pipeline change
as compatible embedding coverage decreases, and under what missingness
patterns does the current hybrid diverge from lexical-only retrieval and a
union-RRF diagnostic comparator?

## 3. Retrieval-unit definition

### Primary controlled track

The primary retrieval unit is a passage/chunk-like retrieval unit.

The denominator for coverage is the complete eligible retrieval-unit set before
masking.

Removing an embedding must NOT:

- remove the document;
- remove the retrieval unit itself;
- change authorization;
- change query text;
- change qrels/gold labels.

Only dense compatibility is manipulated.

### External retrieval track

External datasets retain their published source-document/qrels semantics.

When external documents are chunked for Aqlyra ingestion, evaluation may map
retrieved chunks back to their parent document IDs for external document-level
metrics.

Chunk-level and document-level metrics must never be silently pooled into one
metric.

## 4. Benchmark tiers

### Tier A — Controlled natural-language diagnostic

- 48 source documents.
- 240 canonical queries.
- Five query categories:
  - lexical-anchor;
  - semantic paraphrase;
  - entity+attribute;
  - multi-hop;
  - distractor-heavy.
- 7 coverage levels:
  1.00, 0.90, 0.75, 0.50, 0.25, 0.10, 0.00.
- 10 fixed masking seeds.
- Natural-language queries are required.
- Exact identifier-style queries may appear only in the dedicated
  lexical-anchor subset.
- Multi-hop questions may have multiple gold supporting units.

### Tier B — External natural-language retrieval

Initial development datasets:

- SciFact test;
- NFCorpus test.

FiQA-2018 may be added as a development dataset after the first two datasets
run reproducibly.

LoTTE and BRIGHT remain optional external-stress extensions.

External datasets must use their published qrels.

## 5. Retrieval conditions

For every paired evaluation:

1. Lexical-only
2. Dense-only
3. Aqlyra current hybrid
4. Research-only union-RRF comparator

The current production implementation must be evaluated without changing its
production retrieval behaviour.

A future coverage-aware fallback may be evaluated only after the baseline
characterization is complete.

## 6. Fixed controls

Hold constant wherever applicable:

- corpus contents;
- retrieval-unit boundaries;
- canonical query text;
- gold/qrels;
- user identity;
- authorization scope;
- embedding model;
- embedding dimension;
- tokenizer;
- chunking policy;
- top-k;
- candidate multiplier;
- RRF configuration;
- generation configuration when downstream RAG is tested;
- evaluation code;
- runtime environment.

Coverage masking is the only primary intervention.

## 7. Coverage definition

For each experimental corpus:

AEC = compatible_embedding_units / eligible_units

At each requested coverage c, the experiment must retain exactly the target
number of compatible units:

compatible_count = floor(c * eligible_count)

The implementation must record both the requested coverage and the achieved
coverage.

## 8. Masking policies

### RANDOM

Primary masking policy.

Units are sampled uniformly at the requested coverage.

Random masking is corpus-level and therefore the same mask can be reused for
all queries in a corpus/seed pair.

### RELEVANCE-DEPLETED

Secondary adversarial diagnostic.

For answerable queries, preferentially remove compatible embeddings from
gold-relevant units until the target coverage is reached. If additional
units must be masked to reach the exact target, mask from the remaining
non-relevant eligible units.

This policy is query-specific.

### RELEVANCE-PRESERVING

Secondary control.

Preferentially retain gold-relevant units subject to the exact requested
coverage. If coverage is too low to retain every relevant unit, retain as many
as possible before selecting additional units.

This policy is query-specific.

Relevance-aware masks must never be presented as estimates of naturally
occurring prevalence. They are stress/control conditions.

## 9. Gold judgments

Gold relevance judgments are frozen before retrieval runs.

A query may have multiple gold supporting units.

The gold dataset is separate from system outputs and run metadata.

For external datasets, published qrels are authoritative.

For controlled datasets, reviewed annotations must be versioned and immutable
during an experiment batch.

## 9A. Conflict-query contract

A conflict query represents a case where two or more evidence units contain
materially contradictory information relevant to the same question.

For every conflict query:

- at least two positive qrels are required;
- at least two positive qrels must belong to the same conflict group;
- contradictory units must be explicitly marked in qrels;
- the query record must contain a conflict_group_id;
- the query record must contain a non-empty resolution_rule.

Resolution rules may require:

- a justified latest-version or authoritative-source resolution; or
- explicit uncertainty reporting when the evidence does not justify selecting
  one state.

Conflict cases must never be silently treated as ordinary answerable queries.

## 10. Primary metrics

Primary retrieval metrics:

- Recall@5
- MRR@10
- evidence/support-unit recall where applicable

Secondary:

- Recall@1
- Recall@10
- nDCG@10 where graded qrels are available
- rank displacement relative to full coverage
- relative retention
- rank overlap/stability across masking seeds
- current-hybrid vs union-RRF gap

Coverage analysis:

- metric versus AEC;
- relative retention = metric(AEC) / metric(1.00);
- performance difference between current hybrid and union-RRF.

Latency and candidate counts are recorded as diagnostics, not primary outcomes.

## 11. Security invariant

All research conditions must obey the existing authorization boundary.

Required invariant:

unauthorized_retrieval_count = 0

Coverage manipulation must occur only within the already-authorized eligible
retrieval universe.

Any security violation invalidates that run for research interpretation.

## 12. Pairing and statistical unit

The primary statistical unit is query_id.

The same query must be evaluated across coverage levels, masking seeds, and
retriever conditions where applicable.

Coverage levels and masking seeds are repeated conditions, not independent
users/documents.

Later statistical analysis should use paired methods appropriate to the
outcome distribution.

## 13. Reproducibility contract

Every run must record:

- benchmark version;
- dataset version/source;
- dataset checksum;
- Git commit;
- query/document/unit counts;
- embedding provider;
- embedding model;
- embedding dimension;
- retrieval condition;
- top-k;
- candidate multiplier;
- RRF parameters;
- coverage target;
- achieved coverage;
- masking policy;
- masking seed;
- runtime environment;
- run timestamp.

## 14. Leakage controls

Canonical queries must not contain:

- document IDs;
- filenames;
- gold unit IDs;
- coverage values;
- masking policy names;
- condition names;
- expected answers.

Gold annotations and masking decisions must never be inserted into the model
input.

## 15. Phase 3 decision gates

Phase 3 is complete only when:

1. the benchmark schema is frozen;
2. all benchmark data are versioned;
3. masking is deterministic from stored seeds;
4. gold judgments are frozen separately from outputs;
5. at least two external natural-language datasets run end-to-end;
6. current Aqlyra hybrid can be evaluated without production-code changes;
7. authorization invariants pass;
8. raw outputs are reproducibly archived.

Only after these gates should Phase 4 begin.
