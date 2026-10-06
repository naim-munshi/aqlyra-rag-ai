# Phase 3 Content Quality Decision — Tier A v0.3.3

## Status

**PASS — quality-fix release candidate**

## Lineage

- Source: `tier_a_v0.3.2`
- Derived version: `tier_a_v0.3.3`
- Source corpus, qrels, gold answers, answerability labels, query-type labels,
  and evidence mappings were preserved.
- No document retrieval unit was added, removed, or re-labeled.

## Changes

Only query wording was corrected:

1. removed the duplicated authoring pattern `routine routine`;
2. corrected `How much` to `How many` for countable nouns where applicable.

No gold evidence, qrels, or answer semantics were intentionally changed.

## Why a full redesign was not performed

The prior audit showed:

- 240/240 normalized question templates were unique;
- 20 duplicated-word errors were concentrated in one repeated phrase;
- the 104 direct gold/evidence mismatches disappeared under explicit
  time-range normalization, demonstrating representation mismatch rather
  than evidence mismatch.

Therefore a full benchmark rewrite would add unnecessary provenance risk
without evidence that the underlying qrels or information needs were invalid.

## Gate

This version is a **candidate benchmark artifact**, not yet the final frozen
research benchmark. It still requires:

- structural validation;
- semantic/qrel validation;
- human review of query naturalness;
- external benchmark validation;
- reproducible masking checks.

No main experiment should be interpreted as final evidence until those gates pass.
