# Research Direction Update — 2026-09-29

## Status

Research question remains provisional.

## Baseline status

Aqlyra historical semantic embedding provenance has been successfully reproduced:

- 401/401 Granite embedding records reproduced
- model: ibm-granite/granite-embedding-97m-multilingual-r2
- observed model revision: 835ad14087e140460703cf0fae09f97d469d65c2
- minimum cosine similarity: 1.000000000000
- mean cosine similarity: 1.000000000000
- maximum cosine error: 2.639e-13

The existing production database contains:

- 55 documents
- 7 unique users
- 517 chunks/embedding records
- 401 Granite records
- 116 deterministic records
- no document with mixed embedding providers

The production corpus is not yet treated as the public research benchmark.

## Literature saturation update

The original authorization-limited evidence-sufficiency framing is no longer considered a sufficient standalone research gap.

Direct or substantial overlaps include:

1. Partial Evidence Bench:
   authorization-limited evidence, full-corpus and authorized-view oracles,
   completeness awareness, gap reporting, and unsafe completeness.

2. S2G-RAG:
   structured evidence sufficiency and gap judging.

3. Evidence-Graded Decision Authorization:
   evidence sufficiency linked to claim-level authorization, in a clinical setting.

4. Authorization-First Retrieval:
   authorization before semantic retrieval and security exposure evaluation.

5. Pair-ID:
   controlled paired/counterfactual evidence interventions under a fixed
   query, retrieval state, and reader.

6. CiteGuard / CiteGuard-RAG:
   claim-level evidence validation, citation verification, selective answering,
   and grounding/refusal.

## Current candidate

A narrower candidate is authorization-induced provenance transition at
claim level.

Candidate question:

"When an authorization boundary changes while the global corpus, query,
generator, and retrieval policy are held fixed, how do claim-level evidence
support and response behavior change, and can those changes be localized to
the authorization boundary rather than ordinary retrieval/generation error?"

This remains a hypothesis.

## Proposed comparison

For each paired instance:

F = full authorization view
R = restricted authorization view

Hold constant:

- question
- global corpus
- retrieval configuration
- generator configuration
- decoding parameters
- evaluation protocol

Measure per claim:

- support under F
- support under R
- authorized-support delta
- unauthorized-support dependence
- citation transition
- answer transition
- abstention/partial-answer transition

## Novelty gate

The candidate must be rejected or revised if prior literature already
provides an equivalent claim-level, paired authorization-transition
evaluation with the same controlled intervention and attribution analysis.

No "novel", "first", or "SOTA" claim is permitted before this gate passes.
