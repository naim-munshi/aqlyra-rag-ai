# Prior-Art Gate v0.3

Date: 2026-09-29

## Candidate v0.5 — Rejected

RQ-v0.5 proposed studying authorization selectivity,
query-filter correlation, hybrid RRF retrieval, evidence sufficiency, and
adaptive retrieval budgeting.

This candidate is not retained.

### Reasons

1. ACORN (SIGMOD 2024) already studies predicate-constrained vector
   retrieval as hybrid search over vector embeddings and structured
   predicates.

2. Filtered Vector Search literature explicitly identifies filter
   selectivity, cardinality, and data correlation as determinants of
   filtered-search performance.

3. RACORN-1 (2026) explicitly studies adaptive filtered vector search,
   including low selectivity and negative query-filter correlation.

4. Recent enterprise Hybrid-RAG work combines access-control filtering,
   BM25+dense retrieval, RRF, citations, and retrieval/answer evaluation.

5. Evidence-sufficiency literature already studies the downstream effect
   of insufficient retrieved evidence.

Therefore the proposed factor combination is not currently sufficient for
a defensible research contribution.

## Candidate v0.6

RQ-v0.6 changes the object of study from retrieval utility to
mechanism-level causal attribution.

The candidate asks whether an evaluator can distinguish:

- authorization-induced evidence loss,
- retrieval-induced evidence loss,
- evidence-selection/packing loss,
- and no intervention,

when the downstream observable evidence deficit may be similar.

## Existing Related Work

- Legal RAG Bench:
  hierarchical decomposition of retrieval and reasoning failures.

- AgenticRAG-FP:
  controlled intervention for causal failure attribution in agentic RAG.

- Partial Evidence Bench:
  authorization-limited evidence, full-vs-authorized views, completeness,
  and unsafe-completeness evaluation.

- Permission Boundary:
  paired-world permission/noninterference evaluation.

The remaining candidate distinction is the combination of an explicit
authorization-loss intervention with a mechanism-attribution task in
non-agentic access-controlled RAG.

This distinction is NOT CONFIRMED NOVEL.

## Required Next Gate

No benchmark implementation until exact prior-art inspection is complete.
