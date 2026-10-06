# Prior-Art Gate v0.4

Date: 2026-09-29

## Current Candidate

RQ-v0.7:

"To what extent does embedding-index heterogeneity confound the evaluation
of authorization-aware RAG, and can provenance-controlled evaluation
separate retrieval-space effects from genuine authorization effects?"

## Current Assessment

STATUS: CANDIDATE SURVIVES TARGETED SCREEN
NOVELTY: NOT CONFIRMED

## Established Adjacent Work

### RAG reproducibility

ReproRAG studies reproducibility variation caused by embedding models,
retrieval algorithms, precision, hardware, and distributed execution.

### Partial embedding migration

A September 2026 preprint studies RAG memory portability and explicitly
evaluates a 50/50 mixed embedding index, including downstream retrieval
effects.

### Permission-aware RAG

Permission-Aware RAG evaluates access-controlled retrieval and the impact of
access levels on answer quality and scalability.

### Authorization-limited evidence

Partial Evidence Bench evaluates evidence availability under authorization
constraints, including full-corpus and authorized-view reasoning.

## Targeted Intersection Search

Searches conducted for:

- mixed embedding + ACL
- embedding mismatch + permission-filtered retrieval
- partial embedding migration + authorization
- permission-aware RAG + embedding model mismatch
- authorization × embedding interaction
- mixed vector index + ACL
- permission-conditioned embedding migration
- factorial permission-aware retrieval evaluation

No direct peer-reviewed study was identified that matches the complete
proposed intersection:

embedding-index provenance/migration
× authorization condition
× controlled RAG evaluation
× downstream authorization-aware outcomes.

This absence is not treated as proof of novelty.

## Important Counterevidence

Embedding mismatch and version consistency are already recognized engineering
failure modes.

Several production tools and engineering studies recommend strict
model/index consistency, provenance manifests, and controlled migration.

Therefore the contribution cannot simply be:

"embedding models should match the index."

That is established engineering practice.

## What Could Still Be Research-Worthy

A potentially research-worthy contribution would require empirical evidence
that the interaction between:

- authorization restriction, and
- embedding-index heterogeneity

changes estimates of retrieval/evidence/answer behaviour in a measurable
way.

The interaction—not the existence of either problem individually—is the
candidate object.

## Next Gate

Run the preregistered pilot.

Do not write "novel", "first", "new benchmark", or "SOTA" based on this gate.

After the pilot, compare the observed mechanism against:

- ReproRAG,
- the 50/50 migration study,
- Permission-Aware RAG,
- Partial Evidence Bench,
- and any newly discovered work cited by those papers.
