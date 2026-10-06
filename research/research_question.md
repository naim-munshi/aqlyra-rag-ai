# Aqlyra Research Question

## Research Project

Aqlyra — Authorized-Evidence Sufficiency and Abstention in
Document-Grounded Retrieval-Augmented Generation

---

## Working Title

When Evidence Exists but Cannot Be Used:
Evaluating Authorized-Evidence Sufficiency and Abstention in RAG

---

## Primary Research Question

When answer-bearing information exists inside and/or outside a user's
authorized document scope, how does the distinction between globally
available evidence and authorized evidence affect RAG evidence-sufficiency
judgment, answer reliability, abstention behavior, and unauthorized
information disclosure?

---

## Core Research Problem

A document-grounded RAG system does not operate over the entire information
corpus from the perspective of a particular user.

A user may have access to only a subset of the indexed documents.

Therefore, two different notions of answerability exist:

1. Corpus-level answerability:
   The required information exists somewhere in the indexed corpus.

2. Authorized answerability:
   The required information exists within the documents that the current
   user is permitted to access.

These two states may be identical in ordinary cases but can diverge in
multi-user and access-controlled RAG systems.

For example, a question may have a completely supported answer in another
user's document while having no sufficient evidence in the current user's
authorized document scope.

A reliable system should not treat globally available evidence as evidence
that can legitimately support the current response.

This study investigates this boundary experimentally.

---

## Primary Experimental Question

Under controlled combinations of authorized and unauthorized evidence, do
RAG systems correctly distinguish:

- answerable from authorized evidence;
- partially supported by authorized evidence;
- unsupported within authorized scope but answerable from unauthorized data;
- unsupported by the entire corpus;
- conflicting authorized and unauthorized evidence?

---

## Sub-Research Questions

### RQ1 — Authorized Evidence Sufficiency

How does RAG behavior differ when the answer is fully, partially, or not
supported by evidence within the user's authorized document scope?

### RQ2 — Unauthorized Answer Availability

When a correct answer exists in documents outside the user's permitted scope,
does the system appropriately abstain rather than use or expose that
information?

### RQ3 — Evidence and Access Interaction

How does the presence of unauthorized but highly relevant evidence interact
with evidence-sufficiency assessment, retrieval, generation, citation, and
abstention?

### RQ4 — Safety–Utility Trade-off

Can a system reduce unauthorized disclosure without causing excessive
false refusals when sufficient authorized evidence is available?

### RQ5 — Pipeline Placement

How do different placements of authorization filtering and evidence
verification affect these behaviors?

---

## Main Research Hypothesis

For a fixed question and corpus, RAG answerability should depend on the
evidence available within the user's authorized scope rather than merely on
whether supporting information exists somewhere in the global corpus.

This is a hypothesis to be tested experimentally.

---

## Secondary Hypotheses

### H1 — Authorized Sufficiency

When complete supporting evidence exists within the authorized scope,
scope-aware RAG should answer accurately with valid supporting evidence.

### H2 — Unauthorized-Only Evidence

When complete supporting evidence exists only outside the authorized scope,
a scope-aware system should abstain rather than provide an answer derived
from unauthorized information.

### H3 — Leakage Risk

Systems that expose unauthorized evidence to downstream retrieval or
generation stages will have higher unauthorized-information exposure than
systems that constrain the candidate evidence space before generation.

### H4 — False Refusal Trade-off

Stricter evidence-and-scope verification may reduce unauthorized answers but
can increase over-refusal in cases where authorized evidence is partial but
sufficient.

### H5 — Conflict Sensitivity

Conflicts between authorized and unauthorized evidence may produce different
failure patterns from ordinary conflicts occurring entirely within the
authorized evidence set.

---

## Controlled Evidence Conditions

Each question should be evaluated under controlled evidence configurations.

### Condition A — Authorized Full Support

Authorized documents contain sufficient evidence.

Expected behavior:
Answer.

### Condition B — Authorized Partial Support

Authorized documents contain only part of the information needed.

Expected behavior:
Answer only when the required conclusion is legitimately supported;
otherwise abstain.

### Condition C — Unauthorized Full Support

The answer is fully supported outside the user's authorized scope, while
authorized documents do not provide sufficient support.

Expected behavior:
Abstain.

### Condition D — No Support

Neither authorized nor unauthorized documents contain sufficient evidence.

Expected behavior:
Abstain.

### Condition E — Authorized Conflict

Authorized documents contain contradictory evidence.

Expected behavior:
Resolve only when the evidence supports a justified resolution; otherwise
abstain or explicitly report uncertainty.

### Condition F — Authorized / Unauthorized Conflict

Authorized evidence supports one state while unauthorized evidence supports a
different state.

Expected behavior:
The response must remain determined solely by authorized evidence.

### Condition G — Unauthorized Distractor

Highly relevant-looking evidence exists outside the authorized scope.

Expected behavior:
Unauthorized evidence must not influence the response.

---

## Candidate System Variants

The exact variants will be finalized after the literature review and Aqlyra
implementation audit.

### Variant A — Scope-Aware Reference

Authorization
→ Retrieval
→ Evidence Verification
→ Generation
→ Citation / Grounding
→ Repair / Abstention

### Variant B — Retrieve-Then-Filter

Broad Retrieval
→ Scope Filtering
→ Evidence
→ Generation
→ Verification

### Variant C — Retrieval Without Evidence Verification

Authorization
→ Retrieval
→ Generation

### Variant D — Scope-Aware Verification

Authorization
→ Retrieval
→ Evidence Sufficiency
→ Generation
→ Citation / Grounding
→ Repair / Abstention

These variants are experimental candidates and are not themselves claimed as
novel methods.

---

## Primary Evaluation Dimensions

### Answer Reliability

- Answer correctness
- Evidence-supported correctness
- Unsupported-claim rate
- Citation precision
- Citation coverage
- Grounding score

### Abstention

- Correct-answer rate
- Correct-refusal rate
- False-answer rate
- Over-refusal rate
- Answer coverage

### Authorization Safety

- Unauthorized evidence retrieval rate
- Unauthorized context exposure rate
- Unauthorized-information disclosure rate
- Scope-violation rate

### Efficiency

- End-to-end latency
- Number of model calls
- Verification overhead
- Token / inference cost

---

## Critical Distinction

The study must distinguish at least the following states:

    Globally Answerable
    Authorized Answerable
    Globally Answerable but Unauthorized
    Globally Unanswerable
    Authorized Evidence Conflicting

This distinction is central to the experimental design.

---

## Experimental Principle

The same question, documents, language model, embedding model, retrieval
parameters, prompt, and runtime environment should be used across matched
conditions.

The principal manipulated variables should be:

- authorization scope;
- evidence availability;
- evidence conflict;
- evidence quality;
- verification configuration;
- pipeline ordering.

---

## Intended Research Contribution

The intended contribution is a controlled evaluation framework for studying
the interaction between evidence sufficiency and authorization scope in
document-grounded RAG.

The study aims to determine whether a RAG system should evaluate evidence
sufficiency over the global corpus or over the evidence that is legitimately
available to the current user, and to quantify the resulting effects on:

- correctness;
- grounding;
- abstention;
- false answers;
- over-refusal;
- unauthorized disclosure.

A stronger novelty claim must only be made after systematic literature
review confirms that this specific interaction has not already been
adequately studied.

---

## Explicit Non-Claims

This research does NOT initially claim that:

- Aqlyra is state of the art;
- authorization-first retrieval is universally optimal;
- evidence sufficiency verification is novel by itself;
- selective refusal is novel by itself;
- citation validation is novel by itself;
- grounding verification is novel by itself;
- Aqlyra eliminates hallucination;
- this is the first secure RAG system;
- this is the first permission-aware RAG system;
- this is the first evidence-sufficiency benchmark.

---

## Research Status

Version: RQ-v0.3
Date: 2026-09-29
Status: Provisional research specification

Next gate:
Systematic literature review and novelty validation.

Benchmark construction must not begin until the next gate is completed.
