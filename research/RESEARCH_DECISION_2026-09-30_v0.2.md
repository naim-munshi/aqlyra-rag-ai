# Aqlyra Research Decision — 2026-09-30 v0.2

## Executive decision

Do **not** use the current Cross-Channel Knowledge-vs-Converse benchmark as the headline paper benchmark.

The benchmark remains useful as an engineering/pilot instrument, but its central comparison overlaps substantially with recent work comparing RAG against broader long-context document exposure. The research program should pivot toward a narrower systems question around **partial compatible embedding coverage during hybrid retrieval, especially inside an authorized tenant/document scope**.

This document records a research decision, not a novelty claim.

## 1. What was completed

### Research-process work
- Broad RAG trustworthiness framing was narrowed repeatedly through explicit prior-art checks.
- Authorization-aware RAG candidates were rejected as headline novelty because authorization-first / permission-aware retrieval is established.
- Stage-wise retrieval/failure attribution candidates were rejected as headline novelty because recent interventional/diagnostic RAG work overlaps.
- Embedding provenance/reproducibility was audited rather than assumed.
- Converse, Knowledge, personal memory, attachment, and conversation-history pathways were traced from code.
- A source/evidence contract map and controlled benchmark specification were produced.
- A 24-document / 120-question synthetic cross-channel pilot was generated and validated.

### Engineering evidence already established
- Current corpus snapshot: 55 documents, 517 chunks, 517 embedding records.
- Historical Granite vectors: 401.
- Deterministic vectors: 116.
- The 401 stored Granite vectors were numerically reproduced within very small tolerance through the verified Hugging Face path.
- Retrieval enforces user/document scope and compatible provider/model/dimension metadata.
- Hybrid retrieval can retrieve a lexical candidate, then fail to keep that candidate in the final fused result when a compatible dense embedding record is unavailable.
- A controlled test already demonstrated the resulting retention pattern under manipulated embedding coverage. This is an engineering behavior, not a research finding.

## 2. Candidate directions explicitly held back

### A. Knowledge vs Converse / RAG vs attachment context
Held as a paper headline because recent work directly compares RAG with whole-document long-context access and measures correctness/cost trade-offs. See:

- The Token Tax of Epistemic Accuracy (arXiv:2606.20898, 2026).
- 5ting / SemEval-2026 Task 8 for explicit separation of dialogue-history use from factual retrieved evidence.

### B. Memory authority / provenance / conflict
Held as a paper headline because recent 2026 work directly benchmarks authority collapse, memory conflicts, provenance-aware memory, and persistent memory behavior. See:

- When Memory Becomes Authority: AuthMem-Bench (arXiv:2608.01679).
- TANGLE / personal-memory ambiguity and conflict.
- MemORAI, SEEM, and Agent Zero Memory for provenance-aware memory.
- Task Matters for controlled context-memory conflict.

## 3. Remaining candidate

### Provisional systems question

> During incremental embedding migration, how does partial **compatible embedding coverage** within the authorized retrieval scope affect hybrid sparse+dense retrieval quality and rank stability, and which coverage-aware fusion policy preserves sparse-only evidence without reducing authorization guarantees?

This is intentionally narrower than “embedding migration” or “hybrid retrieval.” The intervention is the fraction of authorized corpus items that have a dense embedding record compatible with the active query configuration.

## 4. Why this remains worth testing

Standard hybrid retrieval and RRF are already established. The research object is the **partially materialized dense side of a hybrid system during migration/backfill** and the resulting interaction with authorization-scoped candidate availability.

Current Aqlyra has a concrete implementation behavior: lexical-only candidates may be dropped from the final fused result if compatible embedding metadata cannot be found for that chunk.

Recent engineering material and an evaluation blog independently illustrate incomplete vector coverage as a real operational state, but the search did not identify an exact primary research paper matching Aqlyra's combination of:

1. controlled partial compatible embedding coverage;
2. hybrid sparse+dense fusion;
3. authorization-scoped evaluation;
4. explicit measurement of relevant lexical-only candidates being lost because of dense compatibility requirements.

This is an **unresolved literature gap, not an established novelty claim**. The next literature pass must continue searching before any paper claims are made.

## 5. Research contribution candidates

Only these are candidates until experimentally validated:

1. A benchmark/intervention protocol for partial compatible-embedding coverage.
2. A coverage metric defined over the actually authorized candidate population.
3. A failure taxonomy separating true retrieval failure from dense-index coverage failure.
4. A simple coverage-aware fusion intervention that keeps sparse-only candidates eligible for final ranking.
5. Empirical analysis of how migration coverage interacts with query type and authorization scope.

## 6. Falsification criteria

Drop or substantially revise the direction if any of the following occurs:

- Relevant academic prior art is found that already studies the same intervention and measures the same interaction.
- Hybrid retrieval quality remains statistically unchanged across meaningful coverage levels.
- The observed degradation disappears under a technically correct union-RRF implementation, leaving only an Aqlyra-specific implementation bug with no broader systems phenomenon.
- Effects are too corpus-specific to generalize beyond a single synthetic setup.

## 7. Terminology

Use:
- **Converse** = backend `normal` mode.
- **Knowledge** = backend `knowledge` mode.
- **compatible embedding coverage** = fraction of the evaluation-relevant authorized units that possess an embedding record matching provider, model, and dimension requirements for the active retrieval configuration.

Do not call incomplete coverage “model quality.”

Do not call the current mixed production embedding history a mixed-index retrieval defect; the current retriever filters provider/model/dimension compatibility.

## 8. Immediate next stage

1. Build a coverage-intervention benchmark from a complete oracle index.
2. Define coverage levels and repeated masking seeds.
3. Compare lexical-only, dense-only, current Aqlyra hybrid, and union/coverage-aware fusion.
4. Add authorization-scoped slices.
5. Measure retrieval first; only then propagate selected conditions into RAG answer evaluation.
6. Expand literature review before locking RQ-v1.0.
