# Aqlyra Systematic Literature Review Protocol

## Version

SLR-v1.0

## Date

2026-09-29

---

## Objective

Identify prior research that overlaps with the proposed Aqlyra study,
particularly work involving:

1. RAG evaluation
2. evidence sufficiency
3. selective abstention / refusal
4. citation verification
5. grounding verification
6. controlled evidence perturbation
7. authorization-aware retrieval
8. permission-aware RAG
9. multi-tenant information isolation
10. intervention or counterfactual evaluation
11. stage-wise or causal failure analysis
12. evaluation of reliability, safety, and utility trade-offs

The objective is to determine a defensible research gap before benchmark
construction or experimental implementation begins.

---

## Research Question for the Review

What aspects of evidence sufficiency, authorization scope, verification,
abstention, and their interaction in document-grounded RAG remain
insufficiently evaluated by existing research?

---

## Search Sources

Primary search sources:

- ACL Anthology
- arXiv
- OpenReview / official conference proceedings
- IEEE Xplore
- ACM Digital Library
- Springer / Nature
- ScienceDirect

Secondary sources may be used only for discovery.

A discovered paper must be verified against its primary publication or
official preprint before being treated as evidence.

---

## Search Strategy

Search combinations should include:

- "retrieval augmented generation" AND evaluation
- "RAG" AND evidence sufficiency
- "RAG" AND abstention
- "RAG" AND selective refusal
- "RAG" AND citation verification
- "RAG" AND grounding
- "RAG" AND authorization
- "RAG" AND permission
- "RAG" AND multi-tenant
- "RAG" AND access control
- "RAG" AND evidence perturbation
- "RAG" AND counterfactual
- "RAG" AND failure attribution
- "RAG" AND reliability
- "RAG" AND calibration

Searches must include recent literature through 2026.

---

## Inclusion Criteria

Include a paper when at least one condition applies:

1. It proposes or evaluates a RAG system.
2. It evaluates evidence-grounded generation.
3. It studies abstention or refusal from insufficient evidence.
4. It studies citation or grounding verification.
5. It studies retrieval or evidence perturbation.
6. It studies authorization, permissions, privacy, or multi-tenant
   constraints in RAG.
7. It proposes a benchmark or evaluation framework directly relevant to the
   research question.

---

## Exclusion Criteria

Exclude:

- papers unrelated to RAG;
- papers where retrieval is incidental and not part of the research problem;
- purely application-oriented papers without a measurable research
  contribution;
- blog posts and informal articles as evidence;
- duplicate versions of the same work;
- secondary summaries when a primary source is available.

A blog or project page may be retained as a discovery source but must not
replace the primary source.

---

## Evidence Hierarchy

Priority order:

1. Peer-reviewed conference/journal paper
2. Official conference proceedings
3. Official arXiv/preprint
4. Official project repository
5. Author research page
6. Secondary source

The evidence level must be recorded explicitly.

---

## Verification Fields

For every included paper record:

- title
- authors
- publication year
- venue
- publication status
- DOI / arXiv identifier
- primary source URL
- research problem
- dataset / benchmark
- evidence conditions
- retrieval method
- verification method
- authorization handling
- abstention handling
- intervention / perturbation
- evaluation metrics
- major findings
- limitations
- direct overlap with Aqlyra
- potential remaining gap

---

## Overlap Classification

Use one of:

### DIRECT

The prior work studies essentially the same research question or
experimental construct.

### SUBSTANTIAL

The prior work covers a major component or experimental dimension but not
the complete research setting.

### ADJACENT

The work is conceptually related but studies a different research target.

### BACKGROUND

The work provides general methodology or established evaluation practice.

### DISTINCT

The work does not materially overlap with the proposed research question.

---

## Publication Status

Use exact labels:

- Published — peer-reviewed
- Published — proceedings
- Journal article
- Preprint
- Technical report
- Dataset / benchmark paper

Do not describe a preprint as a peer-reviewed publication without evidence.

---

## Novelty Rules

The following claims require explicit supporting evidence:

- first
- novel
- state of the art
- unprecedented
- no prior work
- solves
- guarantees

If equivalent prior work is discovered, narrow or revise the research
question instead of weakening the literature description.

---

## Stopping Rule

The systematic review is not considered complete merely because a target
number of papers has been collected.

The review may be considered sufficiently saturated only when:

1. major research themes are represented;
2. recent 2025-2026 literature has been checked;
3. repeatedly recurring references have been followed;
4. the same candidate research gap persists after direct comparison;
5. newly found papers rarely introduce a materially different relevant
   construct.

---

## Final Gate Before Benchmark Construction

Benchmark construction may begin only after:

- the candidate gap is documented;
- directly overlapping papers are identified;
- the research question has been revised if necessary;
- experimental differentiation from existing work is explicit;
- all major novelty claims are evidence-backed.

---

## Status

SLR-v1.0
Initial protocol established.
Systematic review in progress.
