# Aqlyra Literature / Novelty Review — 2026-09-30

## Purpose

This file records the current overlap assessment after the Aqlyra architecture audit. It is a working prior-art map, not a systematic-review-complete claim.

## High-overlap areas

### 1. Multi-turn RAG

5ting (SemEval-2026 Task 8) explicitly separates conversation history used for intent/coreference from retrieved passages used as exclusive factual grounding. This directly overlaps the idea that conversation history should not silently become factual RAG evidence.

Reference: https://aclanthology.org/2026.semeval-1.254/

### 2. General conversational RAG method comparisons

Alushi et al. (EACL 2026 SRW) provide a systematic comparison of RAG methods across eight conversational QA datasets, including retrieval and answer generation metrics and turn-by-turn analysis.

Reference: https://aclanthology.org/2026.eacl-srw.17/

### 3. Joint memory + long-document reasoning

MemoryDocDataSet (2026) evaluates hybrid questions that require first using conversational memory to identify the relevant document and then extracting the answer from that document. Hybrid questions are a large part of its benchmark.

Reference: https://arxiv.org/abs/2606.04442

### 4. Context–memory conflict

Task Matters (Findings ACL 2026) directly studies controlled conflicts between contextual knowledge and parametric memory and shows that conflict behavior depends on task knowledge requirements.

Reference: https://aclanthology.org/2026.findings-acl.202/

### 5. Provenance-aware long-term memory

MemORAI tracks factual origins at turn level in a provenance-enriched graph. SEEM anchors structured episodic event frames with provenance pointers. Agent Zero Memory stores conversation/file/source history as provenanced memory and uses citation-locked answering.

References:
- https://aclanthology.org/2026.findings-acl.1408/
- https://aclanthology.org/2026.acl-long.277/
- https://arxiv.org/abs/2608.29606

### 6. Evidence sufficiency and abstention

The Evidence Sufficiency Benchmark evaluates answer/abstention behavior across a controlled evidence-quality gradient including partial, absent, irrelevant, and conflicting evidence. This overlaps any standalone claim about “testing whether the system abstains when evidence is insufficient.”

Reference: https://doi.org/10.32604/cmc.2026.086343

### 7. RAG attribution/evaluation

ARES evaluates context relevance, answer faithfulness, and answer relevance. RAGAs provides reference-free RAG evaluation metrics. Source Attribution in RAG studies document-level attribution and interactions such as redundancy and complementarity.

References:
- https://aclanthology.org/2024.naacl-long.20/
- https://aclanthology.org/2024.eacl-demo.16/
- https://arxiv.org/abs/2507.04480

### 8. Authorization-aware RAG

Permission-Aware RAG (IEEE Access 2025) uses IAM-based access filtering. Authorization-First Retrieval (TrustNLP 2026) formalizes authorization-before-retrieval as a least-privilege invariant and evaluates controlled enterprise corpora.

References:
- https://doi.org/10.1109/ACCESS.2025.3628960
- https://aclanthology.org/events/trustnlp-2026/

## Consequence for Aqlyra

The following are not acceptable as headline novelty claims without a much narrower additional contribution:

- “A new multi-turn RAG system”
- “provenance-aware memory”
- “citation-aware RAG”
- “evidence sufficiency / abstention benchmark”
- “authorization-aware RAG”
- “memory + documents”
- “conversation history vs retrieved evidence”

## Remaining candidate space

The working candidate is not a new retrieval method and not a new memory representation. It is an empirical question about **evidence-contract differences for the same source/question pair inside one assistant product**.

The proposed comparison is:

K = Knowledge: authorized retrieval + grounded answer/citation enforcement.

C = Converse: exact same source as attachment + contextual generation without strict citation gating.

N = Converse control: no source attachment.

The candidate contribution would be a controlled measurement of whether the evidence contract itself changes factual support, unsupported source-dependent claims, attribution, and abstention behavior.

## Important novelty caveat

This candidate may still overlap with prior work once the search is expanded to:

- “same source / different context presentation” experiments;
- attachment-based document QA versus RAG;
- citation-required versus citation-free generation;
- source-access contract comparisons;
- controlled evidence exposure studies;
- enterprise chat products that compare retrieval and file-context pathways.

Therefore RQ-v1.0 remains provisional until the benchmark pilot and a targeted final prior-art search are completed.
