# Aqlyra Phase 3 Benchmark v0.3

This directory is the active development benchmark specification for the
current candidate research direction:

**Hybrid Retrieval Under Partial Compatible-Embedding Coverage**

## Version status

v0.3 supersedes v0.2 for active benchmark construction.

v0.2 is intentionally preserved as a historical development artifact.

## Current research boundary

The primary experiment studies incomplete compatible dense-embedding coverage
inside a hybrid lexical+dense retrieval pipeline.

Authorization is held fixed and remains a hard security invariant rather than
the primary experimental factor.

## Active systems

- lexical-only;
- dense-only;
- current Aqlyra hybrid;
- union-RRF diagnostic comparator.

## Active coverage levels

1.00, 0.90, 0.75, 0.50, 0.25, 0.10, 0.00.

## Important separation

Gold judgments, masking configuration, run metadata, retrieval outputs, and
aggregated metrics are separate artifacts.

Do not place run-specific fields such as model configuration or masking seeds
inside the gold judgment file.

## Historical artifacts

The earlier K/C/N Knowledge-vs-Converse benchmark files remain in the parent
research directory as historical research work. They are not the active
benchmark specification for this research direction.

## Research-integrity rule

No novelty, first, SOTA, superiority, or causal claim is permitted from the
benchmark design alone.

The benchmark must be able to produce a null result and must preserve all
negative findings.
