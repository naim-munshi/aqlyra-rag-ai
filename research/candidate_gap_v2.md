# Candidate Gap v2

Date: 2026-09-29
Status: CANDIDATE ONLY — NOT CONFIRMED NOVEL

## Literature Update

The previous candidate centered on authorization-limited evidence sufficiency and abstention.

That framing is no longer sufficient as a novelty claim because Partial Evidence Bench (May 2026) directly evaluates authorization-limited evidence using ACL-partitioned corpora, full-corpus and authorized-view oracles, completeness judgments, gap reports, and unsafe completeness behavior.

Evidence Sufficiency Benchmark further covers controlled evidence sufficiency levels and abstention calibration.

S2G-RAG covers structured evidence sufficiency and gap judging during iterative retrieval.

Evidence-Graded Decision Authorization covers evidence grading and claim-level authorization in a clinical AI setting.

CiteGuard-RAG covers validation-centered RAG with retrieval, citation validation, grounding, abstention, and regeneration.

Authorization-First Retrieval covers authorization-before-retrieval in multi-agent RAG.

## Candidate Remaining Gap

A potentially narrower and testable gap is the evaluation of **claim-level authorization dependence under paired authorization interventions in RAG**.

The candidate distinction is:

- task-level completeness vs claim-level support,
- static authorization partitions vs paired full/restricted intervention,
- answer correctness vs explicit dependence of individual claims on authorized vs unauthorized evidence,
- single-condition evaluation vs within-instance comparison of the same question under different authorization views.

This gap is NOT YET CONFIRMED.

## Why This May Matter

A response can be locally plausible and even well-cited while containing multiple claims with different evidence status.

For example:

- Claim A: fully supported by authorized evidence.
- Claim B: supported only by evidence outside the user's authorization.
- Claim C: unsupported by either view.

A task-level completeness score may not expose this claim-level structure.

The proposed study would test whether authorization changes cause predictable changes in claim support and response behavior, while holding the underlying question and global corpus fixed.

## Required Validation

The candidate must be rejected or revised if prior work is found that already provides:

1. paired full/restricted authorization interventions,
2. claim-level authorization-aware RAG evaluation,
3. explicit unauthorized-evidence dependence measurement,
4. equivalent benchmark or metric design.

No novelty statement should be made until these checks are completed.
