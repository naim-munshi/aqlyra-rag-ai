# Aqlyra Research Review Summary — 2026-09-30

## Assessment

The research process is in good shape, but the current headline candidate should change before a full benchmark run.

### Strong work already completed

- Multiple candidate RQs were rejected rather than defended after close prior-art checks.
- Production engineering was separated from research claims.
- Embedding provenance was experimentally verified.
- Retrieval and memory isolation behavior was tested.
- Converse/Knowledge terminology and code paths were traced.
- A synthetic benchmark was built with explicit gold evidence and reproducibility metadata.
- Security/authorization behavior is being treated as an invariant/control, not as an unsupported novelty claim.

### Work that should now be frozen/archived

The Cross-Channel Knowledge-vs-Converse benchmark should not be used as the paper's primary contribution because recent RAG-vs-long-context work makes the core comparison too close.

The memory authority/provenance direction should remain in the literature review but not be promoted to the main RQ because direct 2026 benchmark work already covers authority collapse and memory conflict/provenance.

### Current candidate worth testing

Partial compatible embedding coverage during hybrid retrieval, with explicit measurement inside authorized scopes.

The novelty status is **unproven**. The next phase is a controlled retrieval experiment, not a paper claim.

## Decision gate

Do not create `research_question_v1.0` yet.

Create it only after:

1. the remaining literature search is expanded;
2. the coverage pilot shows a stable measurable effect;
3. a mitigation intervention has a defensible causal interpretation;
4. authorization remains invariant;
5. results replicate across query/corpus strata.
