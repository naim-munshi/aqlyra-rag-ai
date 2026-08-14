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

## Query Rewrite Experiment

Query rewriting was evaluated separately using the same controlled corpus:

- 10 synthetic documents
- 70 chunks
- 20 labeled queries
- Candidate retrieval depth: 15
- Query rewriter: Groq `openai/gpt-oss-20b`
- Reranker: Groq `openai/gpt-oss-20b`
- Embeddings: `deterministic-sha256-v1`

The original user question remains authoritative for reranking and final
answer generation. The rewritten query is used only for vector and lexical
candidate retrieval.

### Hybrid Retrieval at K=5

| Configuration | Hit Rate | Recall | MRR |
|---|---:|---:|---:|
| No query rewrite | 0.450 | 0.425 | 0.237 |
| Groq query rewrite | 0.500 | 0.500 | 0.218 |

Query rewriting improved candidate coverage in this run, while raw hybrid
ordering was mixed because MRR decreased.

### Hybrid + LLM Reranker

| K | Metric | No Rewrite | Query Rewrite | Delta |
|---|---|---:|---:|---:|
| 1 | Hit Rate | 0.400 | 0.550 | +0.150 |
| 1 | Recall | 0.375 | 0.525 | +0.150 |
| 1 | MRR | 0.400 | 0.550 | +0.150 |
| 3 | Hit Rate | 0.600 | 0.650 | +0.050 |
| 3 | Recall | 0.575 | 0.625 | +0.050 |
| 3 | MRR | 0.483 | 0.600 | +0.117 |
| 5 | Hit Rate | 0.600 | 0.700 | +0.100 |
| 5 | Recall | 0.575 | 0.675 | +0.100 |
| 5 | MRR | 0.483 | 0.610 | +0.127 |

On this controlled run, query rewriting followed by hybrid retrieval and
LLM reranking produced better final ranking metrics than the corresponding
run without query rewriting.

These results should not be interpreted as semantic embedding quality:
candidate generation still used deterministic, non-semantic embeddings.
The LLM query rewriter and reranker are also non-deterministic, so
run-to-run variance is possible.

Query rewriting therefore remains feature-gated and disabled by default
until broader evaluation with semantic embeddings and repeated runs is
available.
