# External BEIR Mapping v0.1

Status: research protocol
Purpose: define the mapping from BEIR datasets to the external
validation track.

## General mapping

One BEIR corpus record is treated as one retrieval unit.

BEIR corpus documents are not re-chunked with the Aqlyra PDF
chunking pipeline.

Original BEIR query text is preserved.

Original BEIR qrels semantics are preserved.

Evaluation uses the qrels-driven test query set rather than treating
all raw query records as evaluation queries.

No authorization manipulation is applied to the external dataset.

## SciFact

Dataset:
SciFact

Canonical test subset:
300 test query IDs

Test qrels:
339 relevance records

Unique relevant corpus records:
283

## NFCorpus

Dataset:
NFCorpus

Canonical test subset:
323 test query IDs

Test qrels:
12,334 relevance records

Unique relevant corpus records:
3,128

## Retrieval-unit rule

The BEIR document ID is the external retrieval-unit identifier.

No document is deleted to simulate missing embeddings.

Partial compatible-embedding coverage is represented by masking
dense eligibility while retaining the lexical retrieval universe.

## System conditions

The external track is designed to compare:

1. lexical-only
2. dense-only
3. current Aqlyra hybrid
4. union-RRF diagnostic comparator

The comparator is diagnostic and is not assumed to be superior.

## Interpretation

External BEIR evaluation is used as a transfer-validation track.
It must not be pooled numerically with the Tier-A chunk-level results
when the retrieval units and evaluation semantics differ.
