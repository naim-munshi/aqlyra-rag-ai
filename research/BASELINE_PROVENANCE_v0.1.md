# Aqlyra Research Baseline Provenance v0.1

Date: 2026-09-29

Status: PROVISIONAL — not yet frozen as Research Baseline v1.0

## 1. Historical embedding inventory

The production PostgreSQL database currently contains:

- 517 embedding records
- 401 Hugging Face Granite embeddings
- 116 deterministic embeddings

Provider-specific document distribution:

- Hugging Face Granite: 45 documents, 401 chunks/embedding records
- Deterministic: 10 documents, 116 chunks/embedding records
- Mixed-provider documents: 0

Therefore the two embedding corpora are document-disjoint.

## 2. Historical Granite model

Model:
ibm-granite/granite-embedding-97m-multilingual-r2

Dimension:
384

Current Hub revision observed on 2026-09-29:
835ad14087e140460703cf0fae09f97d469d65c2

Task:
feature-extraction

Library:
sentence-transformers

## 3. Reproducibility audit

All 401 stored Granite embeddings were independently regenerated through Aqlyra's historical Hugging Face embedding path.

Results:

- Records verified: 401/401
- Minimum cosine similarity: 1.000000000000
- Mean cosine similarity: 1.000000000000
- Maximum cosine error: 2.639000129534e-13
- Maximum absolute element-wise difference: 2.040713956708e-07
- Mean absolute element-wise difference: 4.462111928555e-09
- Maximum L2 difference: 7.277085331394e-07
- Cosine >= 0.999999: 401/401

Interpretation:

The historical Granite embedding corpus is reproducible to numerical precision using the currently observed model/inference path.

This does NOT establish bit-identical historical inference. The stored pgvector representation and inference response have small numerical differences.

## 4. Deterministic corpus

The deterministic vectors use:

Provider:
deterministic

Model:
deterministic-sha256-v1

Dimension:
384

Records:
116

Documents:
10

These records were created after the Granite corpus and represent later document-ingestion activity. They are not treated as semantic-equivalent to Granite vectors.

## 5. Research corpus policy

The existing production document corpus is not automatically treated as a publication benchmark.

Filename-based metadata inspection identified at least:

- 13 files matching test/demo naming patterns
- 1 file matching a CV/resume naming pattern

These filename classifications are heuristic only and are not content-level classifications.

Private or personal user documents will not be included in a public research benchmark without an appropriate sanitized/research-use basis.

## 6. Baseline decision

The 401 historical Granite vectors are retained as the canonical historical semantic index candidate.

The 116 deterministic vectors are retained for provenance and runtime-history analysis.

No embedding records are deleted.

No production re-indexing is performed at this stage.

## 7. Next research gate

Before Research Baseline v1.0 is frozen:

1. Define a controlled research corpus.
2. Define document ownership/authorization ground truth.
3. Define global answerability vs authorized answerability.
4. Define evidence-support labels.
5. Define abstention/refusal gold labels.
6. Run the baseline pipeline on the controlled benchmark.
7. Record retrieval, evidence sufficiency, abstention, citation, and disclosure metrics.

Production corpus and research benchmark must remain analytically distinct.
