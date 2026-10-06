# Candidate Gap — Partial Compatible Embedding Coverage v0.1

## Current claim level

**Candidate gap only.** Not a verified novelty claim.

## Observed Aqlyra behavior

The current hybrid path runs lexical and dense retrieval, then uses compatibility-constrained embedding lookup when incorporating lexical-only candidates. If a lexical candidate has no compatible provider/model/dimension embedding, it can be omitted from the final hybrid result.

A dedicated local pilot has already demonstrated the engineered retention relationship under manipulated coverage. Because the pilot constructs the missing-embedding condition, its output should not be treated as an empirical paper result.

## Proposed abstraction

Let:

`AEC(q) = |authorized relevant/evaluable chunks with compatible embeddings| / |authorized relevant/evaluable chunks|`

A system-level coverage measure can additionally be defined over all authorized eligible chunks before query-specific relevance is known.

The key distinction is:

- **retrieval failure:** the method did not rank a relevant item;
- **coverage failure:** the item could not participate in the dense leg because its compatible embedding was absent;
- **fusion failure:** a relevant lexical-only item existed but the fusion policy removed/displaced it.

## Prior-art boundary

Hybrid sparse+dense retrieval and RRF are established. Embedding migration is established as an engineering problem. Authorization-aware retrieval is established. Incomplete vector-index coverage has also appeared in current engineering evaluations.

The unresolved question is whether the combination of partial compatible dense coverage, authorization-scoped candidate availability, and hybrid-fusion loss has already been systematically studied in primary research. That search is incomplete.

## What would count as evidence of a broader phenomenon

A useful result would show a reproducible relationship between AEC and retrieval degradation across:

- multiple query types;
- multiple authorization scopes;
- multiple masking seeds;
- multiple corpora or corpus strata.

A useful mitigation study would compare the current compatibility-gated fusion with a union/coverage-aware fusion and show whether retrieval degradation is reduced without authorization leakage.

## What would falsify the research direction

- close primary prior art is found;
- effects exist only because Aqlyra contains an implementation defect and disappear under a correct baseline;
- effect size is negligible across coverage levels;
- results fail to reproduce under changed corpus/query strata.
