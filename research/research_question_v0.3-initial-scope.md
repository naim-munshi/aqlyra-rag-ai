# Aqlyra Research Question

## Research Project

Aqlyra — Controlled Evaluation of Verification and Access-Control Ordering
in Document-Grounded Retrieval-Augmented Generation

---

## Working Title

Order Matters:
Evaluating Verification and Access-Control Ordering in
Document-Grounded Retrieval-Augmented Generation

---

## Primary Research Question

How does the ordering of access-control, retrieval, evidence verification,
grounding, and abstention stages affect the reliability, safety, and
answer–abstention trade-off of document-grounded Retrieval-Augmented
Generation (RAG) under controlled evidence perturbations?

---

## Research Motivation

RAG systems are commonly evaluated by measuring the quality of their final
answers. However, real-world document-grounded systems contain multiple
decision stages between a user query and the final response.

These stages may include:

- document-access authorization;
- retrieval;
- evidence selection;
- answer generation;
- citation validation;
- semantic grounding;
- answer repair;
- abstention.

A system may therefore produce the same final answer under different internal
pipelines while exposing different safety and reliability characteristics.

For example, restricting document scope before retrieval may prevent
unauthorized evidence from entering the retrieval candidate set, while a
system that retrieves first and filters later may produce different
intermediate behavior even when the final answer appears safe.

Similarly, citation validation, semantic grounding, repair, and abstention
may detect or mitigate failures differently depending on where they are
placed in the pipeline.

This study investigates whether the ordering of these stages is itself an
important determinant of RAG reliability and safety.

---

## Core Research Problem

The study treats a document-grounded RAG system as a sequence of controlled
decision stages rather than as a single black-box answer generator.

The central problem is:

    Does verification-stage ordering change what a RAG system answers,
    refuses, repairs, cites, and exposes?

---

## Primary Experimental Question

For a fixed question set, document collection, model, and evidence
conditions, do different orderings of access control and evidence verification
produce statistically different:

- answer correctness;
- evidence-supported correctness;
- citation validity;
- unsupported-claim rates;
- false-answer rates;
- correct-refusal rates;
- over-refusal rates;
- unauthorized-information exposure;
- latency and inference cost?

---

## Sub-Research Questions

### RQ1 — Access-Control Ordering

Does enforcing document scope before retrieval produce different safety and
retrieval behavior from applying scope filtering after retrieval?

### RQ2 — Verification Ordering

Does the position of citation validation and semantic grounding relative to
generation, repair, and abstention affect the rate of unsupported final
answers?

### RQ3 — Evidence Perturbation

How do different pipeline orderings behave when evidence is:

- sufficient;
- partially sufficient;
- irrelevant;
- missing;
- conflicting;
- misleading;
- noisy?

### RQ4 — Safety–Utility Trade-off

How does changing verification order affect the trade-off between answering
more queries and avoiding unsupported or unauthorized answers?

### RQ5 — Computational Cost

What latency and inference-cost differences arise from alternative
verification orderings?

---

## Main Research Hypothesis

The ordering of verification and access-control stages is not behaviorally
neutral.

Different orderings are expected to produce different reliability and safety
profiles even when they contain the same underlying components.

This hypothesis must be tested experimentally and must not be presented as
established fact before evaluation.

---

## Secondary Hypotheses

### H1 — Pre-Retrieval Scope

Enforcing document scope before retrieval will reduce unauthorized evidence
exposure compared with approaches that retrieve from a broader corpus and
filter later.

### H2 — Evidence Verification

Adding post-generation citation and grounding verification will reduce
unsupported final answers relative to generation without verification.

### H3 — Verification Order

Changing the order of verification, repair, and abstention will alter the
balance between false answers and over-refusal.

### H4 — Perturbed Evidence

The effect of pipeline ordering will be larger under conflicting,
misleading, incomplete, or noisy evidence than under clean evidence.

### H5 — Cost

More extensive verification may improve reliability while increasing
latency or inference cost; therefore evaluation must report both quality and
cost rather than quality alone.

---

## Controlled Pipeline Variants

The exact experimental variants will be finalized after the literature
review and implementation audit.

The initial candidate configurations are:

### Pipeline A — Aqlyra Reference

Scope
→ Retrieval
→ Evidence
→ Generation
→ Citation Validation
→ Grounding
→ Repair / Abstention

### Pipeline B — Scope-Control Ablation

Broader Retrieval
→ Scope Filtering
→ Evidence
→ Generation
→ Verification

### Pipeline C — Verification Ablation

Scope
→ Retrieval
→ Evidence
→ Generation
→ Answer

### Pipeline D — Verification Before Repair

Scope
→ Retrieval
→ Evidence
→ Generation
→ Citation / Grounding
→ Repair
→ Abstention

### Pipeline E — Abstention-Oriented Variant

Scope
→ Retrieval
→ Evidence Sufficiency Check
→ Generation
→ Citation / Grounding
→ Repair / Abstention

These are experimental candidates, not claims that the proposed variants are
novel.

---

## Evidence Conditions

Every benchmark item should have an explicit evidence state.

Initial conditions:

1. Sufficient evidence
2. Partial evidence
3. No supporting evidence
4. Irrelevant evidence
5. Conflicting evidence
6. Misleading evidence
7. Noisy / degraded evidence
8. Out-of-scope evidence

The benchmark should preserve the underlying gold answer, gold evidence,
answerability state, and authorization scope.

---

## Primary Dependent Variables

### Reliability

- Answer correctness
- Evidence-supported correctness
- Unsupported-claim rate
- Citation precision
- Citation coverage
- Grounding score

### Abstention

- Correct-refusal rate
- False-answer rate
- Over-refusal rate
- Answer coverage

### Security

- Unauthorized-information exposure rate
- Unauthorized evidence retrieval rate
- Scope-violation rate

### Efficiency

- End-to-end latency
- Verification latency
- Model calls
- Token / inference cost

---

## Experimental Principle

All pipeline variants must be compared under matched conditions.

Unless a specific experiment requires otherwise, the following must remain
fixed:

- question set;
- documents;
- gold evidence;
- model;
- embedding model;
- prompt;
- retrieval parameters;
- random seed / sampling configuration;
- hardware/runtime environment.

The independent variable should be the pipeline configuration or evidence
condition being studied.

---

## Research Contribution Target

The intended contribution is NOT simply a new RAG application.

The target contribution is a controlled experimental framework for studying
whether the placement and ordering of access-control and evidence-verification
stages changes the reliability, safety, abstention behavior, and cost of
document-grounded RAG.

A stronger contribution claim may only be made after a systematic literature
review confirms that equivalent experimental frameworks do not already exist.

---

## Explicit Non-Claims

This research does NOT initially claim that:

- Aqlyra is state of the art;
- Aqlyra eliminates hallucination;
- pre-retrieval authorization is universally optimal;
- grounding guarantees factual correctness;
- citation validation guarantees correctness;
- one pipeline ordering is universally best;
- this is the first study of RAG failure attribution;
- this is the first study of selective refusal;
- this is the first study of authorization-aware RAG.

All such claims require direct evidence from literature and experiments.

---

## Research Status

Version: RQ-v0.2
Date: 2026-09-29
Status: Provisional research specification

Important:
This document defines the research hypothesis and experimental direction.
The final research question must be validated against a systematic literature
review before benchmark construction begins.
