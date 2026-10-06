# Phase 3 — Tier A Controlled Corpus Plan v0.3

## Purpose

Define the structure of the controlled natural-language benchmark before
writing benchmark content.

This plan is a construction contract, not experimental evidence.

## Corpus size

- 48 source documents
- 8 domain strata
- 6 documents per stratum
- 6 retrieval units per document
- target retrieval-unit count: 288

Each retrieval unit is immutable once the benchmark release is frozen.

## Domain strata

| Stratum | Documents | Purpose |
|---|---:|---|
| STR01 | 6 | Technology / software systems |
| STR02 | 6 | Healthcare / public health |
| STR03 | 6 | Finance / consumer finance |
| STR04 | 6 | Transportation / logistics |
| STR05 | 6 | Education / training |
| STR06 | 6 | Environment / infrastructure |
| STR07 | 6 | Public policy / administration |
| STR08 | 6 | Consumer / operational information |

The domains are used to diversify language and distractor patterns. They do not
constitute a claim that the resulting corpus represents real-world RAG usage.

## Document design

Each document contains exactly six retrieval units:

1. primary fact or definition;
2. related attribute;
3. entity or temporal detail;
4. secondary supporting fact;
5. distractor information;
6. contextual or cross-reference information.

Documents should contain enough internal structure to support both direct and
multi-unit queries.

## Query allocation

Each document receives exactly five canonical questions:

1. lexical-anchor;
2. semantic-paraphrase;
3. entity+attribute;
4. multi-hop;
5. distractor-heavy.

Total:

48 documents × 5 questions = 240 canonical questions.

## Answerability distribution

The five query positions are not identical in answerability across every
document.

Target distribution across the full Tier A set:

- 192 answerable queries;
- 24 unanswerable queries;
- 24 conflict/uncertainty queries.

This corresponds to:

- 80% answerable;
- 10% globally unanswerable;
- 10% conflicting or uncertainty-sensitive.

The exact assignment is fixed by the query-allocation file and must not be
changed after annotation begins without creating a new benchmark version.

## Evidence structure

A query may have:

- one relevant retrieval unit;
- multiple relevant retrieval units;
- conflicting relevant units for designated conflict queries.

Multi-hop questions must have at least two supporting retrieval units.

Unanswerable questions must have no positive gold qrels in the declared
evaluation scope.

## Distractor policy

Distractor units should be topically related enough to create a plausible
retrieval competition but must not contain the answer unless explicitly
classified as conflicting evidence.

Do not use document IDs, filenames, benchmark condition labels, coverage
values, or masking terminology in canonical question text.

## Controlled authoring

Each source document must record:

- source_doc_id;
- document_version;
- source_type;
- source_reference;
- license;
- unit_order;
- content_hash_sha256.

For synthetic content, source_reference must state that the document was
internally authored for the controlled benchmark.

## Query authoring

Each query must record:

- stable query_id;
- source document relationship;
- question;
- question_type;
- answerability;
- gold_answer when applicable;
- scope_id for the controlled scope;
- reviewer annotations.

Gold evidence is stored separately in qrels.

## Reproducibility rule

The final Tier A benchmark release must be reconstructable from:

1. the corpus authoring records;
2. the query allocation matrix;
3. the frozen document texts;
4. the frozen gold judgments.

No model generation step may be the sole source of benchmark ground truth.
