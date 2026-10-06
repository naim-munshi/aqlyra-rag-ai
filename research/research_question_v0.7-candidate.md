# Research Question v0.7 — Candidate

Status: PROVISIONAL / NOVELTY NOT CONFIRMED
Date: 2026-09-29

## Candidate Research Question

To what extent does embedding-index heterogeneity confound the evaluation of
authorization-aware RAG, and can provenance-controlled evaluation separate
retrieval-space effects from genuine authorization effects?

## Motivation

Authorization-aware RAG evaluation commonly varies access conditions and
measures retrieval, answer quality, completeness, or leakage.

Separately, RAG reproducibility research has established that embedding
model choice and embedding/index changes can materially alter retrieval
results.

This creates a potential evaluation confound:

A system may appear to degrade under a restricted authorization condition
because fewer authorized documents remain available, but the measured
difference may also be affected by heterogeneous or mismatched embedding
spaces.

Conversely, an embedding-index problem may reduce authorized retrieval
quality even when the authorization mechanism itself is correct.

## Controlled Factors

### Embedding index composition

- 100% Encoder A
- 75% Encoder A / 25% Encoder B
- 50% Encoder A / 50% Encoder B
- 25% Encoder A / 75% Encoder B
- 100% Encoder B

### Query encoder

- Encoder A
- Encoder B

### Authorization view

- full corpus
- restricted authorized corpus

The global corpus, query set, authorization policy, generator, decoding
parameters, and evaluation protocol remain fixed within paired comparisons.

## Primary Evaluation Question

When authorization conditions are held constant, how much variation in
retrieval and downstream RAG performance is introduced by embedding-index
heterogeneity?

When embedding conditions are held constant, how much variation is caused
by authorization restriction?

Can these effects be statistically separated?

## Candidate Outcomes

Retrieval:

- Recall@k
- MRR
- nDCG@k
- authorized evidence recall
- rank displacement

Evidence:

- sufficient-evidence rate
- evidence coverage
- context survival

Generation:

- supported-answer rate
- unsupported-answer rate
- appropriate abstention
- citation support

Security:

- unauthorized exposure rate
- unauthorized citation rate

Operational:

- latency
- embedding/query cost

## Candidate Analytical Model

A factorial or mixed-effects analysis should estimate the contribution of:

- authorization condition,
- embedding-index composition,
- query-encoder/index compatibility,
- and their interaction.

The key quantity is the interaction between authorization and embedding
heterogeneity.

If the interaction is non-negligible, authorization-only comparisons may be
confounded by vector-space conditions.

## Hypothesis

H1:
Embedding-index heterogeneity changes retrieval outcomes even when
authorization policy is unchanged.

H2:
Authorization restriction and embedding heterogeneity interact in
downstream evidence sufficiency.

H3:
A provenance-controlled evaluation protocol provides more stable
authorization-effect estimates than an uncontrolled mixed-index evaluation.

These are hypotheses only.

## Candidate Contribution

Potential contribution:

A controlled methodology for evaluating authorization-aware RAG while
explicitly treating embedding-index provenance as an experimental factor.

The contribution would be an evaluation protocol and empirical analysis,
not a claim of a new retrieval algorithm.

## Prior-Art Boundary

Relevant prior work includes:

- ReproRAG: RAG reproducibility across embedding models and other
  environmental factors.
- Memory-portability studies: partial mixed embedding migration and its
  downstream effect.
- Permission-Aware RAG: access-level effects on answer quality and latency.
- Authorization-First Retrieval: structural authorization constraints.
- Partial Evidence Bench: authorization-limited completeness behavior.

The candidate must be rejected or revised if prior work already evaluates the
interaction between embedding-index heterogeneity and authorization-aware
RAG under a controlled factorial design.

## Non-Claims

No claim is made that this is:

- first,
- novel,
- SOTA,
- superior,
- or guaranteed publishable.

## Required Validation

1. Search for mixed-index experiments with ACL/authorization factors.
2. Search for embedding mismatch experiments with permission-filtered
   retrieval.
3. Inspect ReproRAG and partial-migration implementations.
4. Search for interaction/factorial evaluation in permission-aware RAG.
5. Confirm whether downstream authorization metrics are reported separately
   from retrieval-space effects.

Only after this gate can RQ-v1.0 be considered.
