# Research Question v0.8 — Candidate

Status: PROVISIONAL / NOVELTY NOT CONFIRMED
Date: 2026-10-06

## Candidate Research Question

How does retrieval performance in a hybrid lexical+dense RAG pipeline change
as the proportion of eligible retrieval units with embeddings compatible with
the active dense retriever decreases, and under what missingness patterns does
the current hybrid fusion diverge from lexical-only retrieval and a union-RRF
diagnostic comparator?

## Research Object

The primary object of study is incomplete compatible dense-embedding coverage
inside a hybrid retrieval pipeline.

Coverage is defined over the fixed eligible retrieval universe before
masking:

AEC = compatible_embedding_units / eligible_units

The benchmark does not remove documents or change authorization when coverage
is manipulated. Only embedding compatibility is changed.

## Primary Systems

1. Lexical-only
2. Dense-only
3. Aqlyra current hybrid
4. Research-only union-RRF comparator

The union-RRF comparator is diagnostic and is not assumed to be a better
method.

## Primary Controlled Variable

Compatible embedding coverage:

- 1.00
- 0.90
- 0.75
- 0.50
- 0.25
- 0.10
- 0.00

## Primary Hypothesis

H1:
As compatible embedding coverage decreases, retrieval performance of dense
retrieval and the current Aqlyra hybrid changes measurably relative to the
full-coverage condition, and the magnitude/pattern of change depends on which
retrieval units lose compatible embeddings.

## Secondary Questions

1. Does the current hybrid preserve lexical evidence when compatible dense
   coverage is incomplete?
2. Does its behaviour differ from a union-RRF fusion that retains lexical-only
   candidates?
3. How sensitive are the observed effects to random versus
   relevance-correlated missingness?
4. Does retrieval rank stability change as compatible coverage decreases?

## Authorization Constraint

Authorization is NOT a manipulated research factor in this candidate.

All primary experiments operate over a fixed authorized eligible set.

Unauthorized retrieval is a hard security invariant and must remain zero.

A separate scope-aware stress track may be used to verify that research
instrumentation does not weaken authorization boundaries.

## Benchmark Principle

The benchmark must use natural-language questions and realistic distractors.
The earlier identifier-style pilot remains diagnostic only and is not treated
as semantic retrieval evidence.

## Non-Claims

No claim is made that this phenomenon is:

- novel;
- first;
- state of the art;
- universally important;
- representative of all RAG systems;
- or caused by embedding coverage alone in all production settings.

Those claims require additional literature review and controlled evidence.

## Decision Gate

RQ-v1.0 remains unlocked.

The candidate can only be frozen after:

1. the Phase 3 benchmark passes validation;
2. at least two external natural-language retrieval datasets run
   reproducibly;
3. the main effect is measurable or produces a scientifically meaningful
   null result;
4. the effect is not explained by an implementation artifact alone;
5. the closest prior work is re-checked against the final formulation.
