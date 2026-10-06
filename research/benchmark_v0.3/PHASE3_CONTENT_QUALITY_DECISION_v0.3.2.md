# Phase 3 Content Quality Decision v0.3.2

## Decision

Tier A v0.3.1 is retained as a historical draft but is NOT eligible for
research experiments.

A separate v0.3.2 corpus is constructed.

## Reasons for rejecting v0.3.1 as experimental data

The content audit exposed several generator artefacts:

1. repeated and unnatural sentence templates;
2. malformed phrases such as "standard standard" and "per.";
3. some nominally unanswerable questions were potentially answerable from
   surrounding context;
4. some multi-hop questions used semantically artificial capacity arithmetic;
5. distractor evidence was not explicitly identified by unit ID;
6. conflict evidence could be structurally valid while being awkwardly
   expressed.

These are benchmark-construction problems, not experimental findings.

## v0.3.2 corrective principles

The redesign:

- uses domain-specific operational vocabulary;
- removes malformed template composition;
- makes unanswerable questions target information absent from the document;
- makes conflict evidence explicitly contradictory on the queried attribute;
- uses multi-unit evidence for multi-hop questions;
- records exact distractor unit IDs;
- preserves immutable unit hashes;
- keeps all benchmark records in draft status until review.

## Research-integrity decision

No retrieval experiment may use v0.3.1.

The v0.3.2 corpus is also NOT publication-frozen until structural and semantic
review passes.
