# Prior-Art Gate v0.2

Date: 2026-09-29

## Rejected Candidate

### RQ-v0.4

Claim-level authorization transition under paired full/restricted
authorization views.

### Reason for rejection

The Permission Boundary independently provides a paired-world permission
benchmark in which:

- authorized projections are held constant,
- restricted state changes,
- public outputs are compared,
- claim/dependency authorization is represented,
- citation and metadata exposure are measured,
- refusal/confidence channels are evaluated,
- and several permission leakage mechanisms are tested.

This creates substantial methodological overlap with RQ-v0.4.

Partial Evidence Bench independently covers authorization-limited evidence,
full-corpus versus authorized-view reasoning, completeness awareness,
gap-report quality, and unsafe completeness.

Therefore RQ-v0.4 is not retained as the primary candidate.

## New Candidate

RQ-v0.5 shifts the object of study from permission-boundary
noninterference to retrieval utility under correctly enforced
authorization.

The candidate crossing is:

authorization selectivity
× query-filter semantic correlation
× retrieval mode
× retrieval/search budget

with downstream evidence sufficiency and answer behavior as outcomes.

## Relevant Prior Art

Filtered Vector Search literature:
filter predicates alter effective search space, recall, and search effort;
selectivity and correlation are explicit variables.

Filtered ANN Search:
evaluates recall/latency under structured filtering and different filter
selectivities/correlations.

Partial Evidence Bench:
authorization-limited evidence and completeness-aware answer behavior.

Permission Boundary:
paired-world permission noninterference and multi-channel leakage.

Authorization-First Retrieval:
authorization-before-retrieval as a least-privilege invariant.

Private-RAG:
integrates permission filtering, reranking, evidence transformation, and
citation attachment.

## Remaining Candidate Gap

The targeted search has not yet identified a peer-reviewed work that
jointly evaluates:

1. authorization selectivity,
2. query-filter semantic correlation,
3. lexical+dense hybrid RRF retrieval,
4. downstream evidence sufficiency,
5. and adaptive retrieval budgeting.

This is a search result, not a novelty conclusion.

## Required Next Validation

- backward citation chasing from filtered-vector-search papers;
- forward citation chasing from 2025-2026 permission-aware RAG papers;
- implementation/code inspection where available;
- exact search for adaptive-k/overfetch under authorization;
- exact search for RRF under filtered retrieval;
- exact search for evidence sufficiency after ACL filtering.

The candidate remains provisional until saturation.
