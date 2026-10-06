# Research Question v0.5 — Candidate

Status: PROVISIONAL / NOVELTY NOT CONFIRMED
Date: 2026-09-29

## Candidate Research Question

How do authorization-filter selectivity and query-filter semantic
correlation affect the retrieval of sufficient authorized evidence in
hybrid RAG, and can adaptive retrieval budgeting recover evidence coverage
without exposing unauthorized content?

## Core Idea

Authorization changes the effective retrieval universe.

A query may have highly relevant documents in the global corpus, but only a
subset may be authorized for the requester. The size and semantic structure
of that authorized subset may therefore affect retrieval quality even when
authorization is correctly enforced.

The candidate study focuses on this retrieval-side effect rather than on
whether authorization exists at all.

## Controlled Factors

A benchmark instance should vary:

1. Authorization selectivity:
   - 5%
   - 10%
   - 25%
   - 50%
   - 100%

2. Query-filter semantic correlation:
   - low
   - neutral
   - high

3. Retrieval mode:
   - lexical/BM25
   - dense semantic retrieval
   - hybrid RRF

4. Candidate/search budget:
   - fixed-k
   - adaptive-k

The query, global corpus, ground-truth evidence, and generator should remain
fixed within each controlled comparison.

## Primary Outcomes

- authorized recall@k
- sufficient-evidence retrieval rate
- relevant-evidence coverage
- context survival after authorization
- appropriate abstention
- supported-answer rate
- latency/search cost
- unauthorized exposure

## Candidate Mechanistic Hypothesis

When authorized evidence is a small or semantically biased subset of the
global corpus, fixed retrieval budgets may provide unstable evidence
coverage even when authorization is correctly enforced.

Increasing the retrieval/search budget may recover authorized evidence
coverage, but the policy must be evaluated separately for security
exposure and computational cost.

## Candidate Contribution

Potential contribution areas:

1. a controlled RAG benchmark crossing authorization selectivity and
   semantic correlation;

2. a retrieval-level analysis of how authorization constraints affect
   evidence sufficiency;

3. comparison of lexical, dense, and hybrid RRF retrieval under identical
   authorization conditions;

4. evaluation of adaptive retrieval budgeting as a utility-preserving
   mechanism under strict authorization.

## Novelty Status

NOT CONFIRMED.

The candidate must be rejected or revised if prior work already provides
an equivalent benchmark or study that jointly evaluates:

- authorization/selectivity conditions,
- query-filter semantic correlation,
- RAG evidence sufficiency,
- hybrid lexical+dense retrieval or RRF,
- and adaptive retrieval budgeting.

## Non-Claims

This document does not claim:

- first work,
- novel benchmark,
- novel metric,
- SOTA,
- superiority,
- or publication acceptance.

All such claims require direct prior-art verification.
