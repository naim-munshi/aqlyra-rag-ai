# Research Question v0.4 — Candidate

Status: PROVISIONAL / NOVELTY NOT CONFIRMED
Date: 2026-09-29

## Candidate Research Question

Under a fixed RAG corpus and query, how does a paired authorization intervention—from full-corpus access to a restricted authorized view—change:

1. claim-level evidence support,
2. completeness signaling,
3. answer / partial-answer / abstention behavior, and
4. dependence on evidence that is outside the authorized view?

## Motivation

Recent work has established several adjacent components:

- authorization-limited evidence and completeness awareness in enterprise agents,
- evidence sufficiency and abstention calibration,
- claim-level evidence authorization in clinical AI,
- sentence/claim-level grounding and citation validation,
- authorization-first retrieval architectures.

The candidate study therefore does not claim novelty from combining these components.

Instead, it proposes a controlled paired intervention in which the underlying question and global corpus remain fixed while the authorization boundary changes. The intended analysis is claim-level rather than only task-level.

## Core Experimental Contrast

For each benchmark instance:

Condition F:
Full evidence authorization.

Condition R:
Restricted authorization in which one or more material evidence sources are outside the caller's authorized view.

The global document set remains unchanged.

The pair shares:

- the same question,
- the same underlying corpus,
- the same ground-truth claims,
- the same generator configuration,
- the same evaluation protocol.

Only the authorization view is changed.

## Candidate Outcomes

### Claim-level support

For every generated claim, identify whether the claim is:

- supported by authorized evidence,
- unsupported by authorized evidence,
- supported only by evidence outside authorization,
- partially supported.

### Completeness behavior

Measure whether the system correctly indicates that the restricted evidence view is sufficient, partially sufficient, or materially incomplete.

### Behavioral outcome

Classify the response as:

- supported answer,
- supported partial answer,
- appropriate abstention,
- unsupported answer,
- unsafe completeness,
- unauthorized-evidence dependence.

## Candidate Metrics

These are proposed metrics, not established standard names.

1. Authorized Claim Support Rate (ACSR)
2. Unauthorized Evidence Dependence Rate (UEDR)
3. Completeness Classification F1
4. Appropriate Abstention Rate
5. Unsupported-Answer Rate
6. Partial-Answer Utility
7. Authorization Sensitivity Gap

Metric definitions will be frozen only after literature review and benchmark pilot.

## Non-Claims

This document does NOT claim:

- first work,
- SOTA,
- novel benchmark,
- novel metric,
- novel architecture,
- superiority over prior systems.

Novelty must be established by broader backward/forward citation chasing and direct implementation-level comparison.

## Required Novelty Checks

Before upgrading this candidate to RQ-v1.0:

- search for claim-level authorization-aware RAG evaluation,
- search for paired/counterfactual authorization interventions,
- search for authorization-conditioned citation/grounding evaluation,
- search for unauthorized-evidence dependence metrics,
- search for full-vs-restricted paired benchmark designs,
- inspect implementations and supplementary material where available.
