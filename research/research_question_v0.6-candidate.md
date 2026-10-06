# Research Question v0.6 — Candidate

Status: PROVISIONAL / NOVELTY NOT CONFIRMED
Date: 2026-09-29

## Candidate Research Question

Can a causal, stage-wise intervention protocol distinguish
authorization-induced evidence loss from ordinary retrieval failure and
downstream evidence-processing failure when these mechanisms produce the
same observable evidence deficit?

## Central Observation

A RAG system may ultimately lack sufficient evidence for several different
reasons:

1. a supporting source exists globally but is excluded by authorization;
2. the source is authorized but the retriever fails to retrieve it;
3. the source is retrieved but lost during evidence selection or packing;
4. sufficient evidence reaches generation but the answer construction or
   validation stage fails.

These mechanisms can produce superficially similar final outcomes.

## Proposed Experimental Principle

Construct paired benchmark instances in which the same question and global
corpus are held fixed while a certified intervention is applied at exactly
one stage.

Candidate interventions:

A. Authorization-induced evidence loss
   A gold-supporting source is outside the requesting user's authorized
   view.

B. Retrieval-induced evidence loss
   The supporting source remains authorized but is made unavailable to the
   retrieval stage through a controlled intervention.

C. Evidence-selection/packing loss
   The supporting source is retrieved but removed before generation.

D. No intervention
   Full authorized evidence path.

The downstream task should be held as constant as practical.

## Primary Diagnostic Task

Given the execution trace and final outcome, determine which intervention
mechanism caused the evidence deficit.

The evaluation should distinguish:

- attribution correctness,
- attribution confusion,
- abstention correctness,
- answer correctness,
- authorized evidence recall,
- unauthorized exposure.

## Candidate Diagnostic Metrics

These are provisional names:

1. Intervention Attribution Accuracy
2. Intervention Attribution Macro-F1
3. Authorization-Loss Confusion Rate
4. False Retrieval-Failure Attribution Rate
5. Appropriate Abstention Rate
6. Unauthorized Exposure Rate

Metric definitions must be frozen after benchmark piloting.

## Research Hypothesis

H1:
A conventional end-to-end correctness score will not reliably distinguish
authorization-induced evidence loss from ordinary retrieval failure.

H2:
A structured stage-wise intervention trace containing authorization,
retrieval, evidence-selection, and final-context lineage will improve
mechanism attribution relative to final-answer-only evaluation.

These are hypotheses and require experimental verification.

## Potential Contribution

Potential contribution areas:

- a controlled failure-attribution benchmark for access-controlled RAG;
- a mechanism-level distinction between policy-induced evidence loss and
  retrieval-induced evidence loss;
- evaluation of whether observable RAG traces identify the true upstream
  failure mechanism;
- analysis of cases in which different upstream mechanisms produce the same
  final evidence sufficiency state.

## Prior-Art Boundary

Existing work already covers:

- generic RAG failure decomposition;
- causal intervention for agentic RAG;
- authorization-limited evidence completeness;
- permission-boundary/noninterference evaluation;
- evidence-sufficiency and abstention evaluation.

The candidate must therefore be rejected if prior work is found with an
equivalent intervention matrix and attribution target specifically for
authorization-aware RAG.

## Non-Claims

No claim is made that this is:

- the first work,
- a novel benchmark,
- a novel metric,
- SOTA,
- superior to prior work,
- or guaranteed publishable.

## Next Gate

Before benchmark implementation:

1. perform backward citation chasing from AgenticRAG-FP;
2. perform backward/forward citation chasing from Legal RAG Bench;
3. inspect Partial Evidence Bench implementation and evaluation protocol;
4. search for access-control-specific failure attribution;
5. search for authorization-aware causal intervention benchmarks;
6. compare trace observability requirements with Aqlyra's current runtime.

Only after this gate should RQ-v1.0 be considered.
