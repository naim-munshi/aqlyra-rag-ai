# Retrieval Baseline

Controlled retrieval benchmark for Aqlyra P7 Advanced Retrieval.

## Corpus

- 10 synthetic documents
- 70 generated chunks
- 20 labeled retrieval queries
- Fixed retrieval depth: 20
- Evaluation cutoffs: K = 1, 3, 5

## Provider

`deterministic-sha256-v1`

This provider does not produce semantic embeddings. The results below
are a retrieval-plumbing and ranking baseline, not a semantic-quality
benchmark.

## Vector vs Hybrid

| K | Vector Hit Rate | Hybrid Hit Rate | Vector Recall | Hybrid Recall | Vector MRR | Hybrid MRR |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0.000 | 0.100 | 0.000 | 0.100 | 0.000 | 0.100 |
| 3 | 0.050 | 0.400 | 0.025 | 0.375 | 0.025 | 0.217 |
| 5 | 0.050 | 0.450 | 0.025 | 0.425 | 0.025 | 0.229 |

Hybrid retrieval combines vector and PostgreSQL lexical retrieval using
reciprocal rank fusion.

The benchmark runner uses a fixed retrieval depth of 20 so that metrics
at K=1, K=3, and K=5 are calculated from comparable rankings.

A semantic embedding provider must be used before making claims about
semantic retrieval quality.
