# Aqlyra Candidate Research Gap

## Date

2026-09-29

## Status

Candidate gap — NOT YET CONFIRMED NOVEL

---

## Established Areas

The current literature establishes substantial prior work in:

- RAG evaluation;
- citation evaluation;
- grounding / faithfulness;
- evidence sufficiency;
- selective refusal;
- evidence perturbation;
- authorization-aware RAG;
- permission-aware retrieval;
- multitenant leakage evaluation;
- failure attribution.

Therefore none of these capabilities alone constitutes a sufficient research
gap for Aqlyra.

---

## Candidate Gap

The proposed study focuses on the distinction between:

1. Global corpus answerability
2. Authorized-scope answerability

A question may be answerable from the global document collection but not
answerable from the documents the current user is authorized to access.

The candidate research problem is to evaluate whether this distinction
changes RAG evidence-sufficiency judgment and abstention behavior.

---

## Candidate Controlled Comparison

For the same question and underlying corpus:

### State A

Supporting evidence exists in authorized documents.

### State B

Supporting evidence exists only in unauthorized documents.

### State C

Supporting evidence does not exist anywhere.

### State D

Authorized evidence is partial or conflicting.

### State E

Authorized and unauthorized evidence provide conflicting information.

The expected system behavior is determined only by authorized evidence.

---

## Candidate Research Contribution

Potential contribution:

A controlled benchmark and evaluation protocol that explicitly separates
global answerability from authorized answerability and measures the effects
on:

- answer correctness;
- evidence-supported correctness;
- false-answer rate;
- correct-refusal rate;
- over-refusal;
- unauthorized disclosure;
- evidence retrieval exposure.

---

## Required Novelty Test

Before this gap can be claimed as novel, the literature review must verify
whether an existing RAG benchmark or paper already evaluates the same
authorized-vs-unauthorized evidence states together with evidence sufficiency
and abstention.

In particular, investigate:

- Permission-Aware RAG;
- Authorization-First Retrieval;
- AAAI Trustworthy Agentic AI authorization work;
- BDI Agent-Based Access Control for Multimodal RAG;
- Evidence Sufficiency Benchmark;
- RefusalBench;
- Evidence-Graded Decision Authorization;
- authority-gap abstention research;
- other 2026 security / RAG benchmarks discovered through citation chasing.

---

## Decision Rule

If equivalent prior work is found:

1. narrow the research question;
2. identify the exact missing experimental dimension;
3. redesign the benchmark.

If equivalent work is not found after saturation:

1. freeze the research question;
2. define the benchmark;
3. preregister the experimental protocol internally;
4. begin implementation.

---

## No Novelty Claim Yet

Do not use:

- novel;
- first;
- unprecedented;
- state of the art;
- no prior work

until the literature review supports the wording.
