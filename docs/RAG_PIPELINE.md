# RAG Pipeline

## What Knowledge mode does

Knowledge mode answers questions from the authenticated user's selected
documents. Authentication establishes the user identity; conversation scope
and ownership checks determine which documents can enter retrieval.

Indexing and answering are separate paths:

```text
upload
→ parse / OCR
→ chunk
→ embed
→ store

authenticated question
→ resolve owned document scope
→ retrieve
→ fuse results
→ build evidence
→ generate
→ validate citations
→ check grounding
→ answer / repair / refuse
```

## 0. Authorization and document scope

Before retrieval, the backend resolves the requested Knowledge document scope.
For conversation requests, that combines the persisted conversation scope with
any newly selected document IDs. It rejects missing, cross-user, or otherwise
invalid document references instead of allowing them into the search filter.

Projects organize conversations but do not widen document access. Project
membership, conversation ownership, and Knowledge document scope remain
separate checks.

## 1. Ingestion

Supported inputs include:

```text
PDF
DOCX
PPTX
XLSX
TXT
Markdown
CSV
PNG
JPG
JPEG
WEBP
```

Files are validated before processing, including maximum upload size,
file-type checks, and bounded Office archive expansion. Newly uploaded files
are created with owner-only Unix permissions. Ownership is recorded on each
document; searchable chunks remain linked to that document so retrieval
can enforce the same user boundary.

Image inputs can be sent through OCR.

## 2. Parsing and chunking

The parser turns each supported file into normalized content.

The chunking step creates smaller searchable units and keeps the source metadata needed later for retrieval and citations.

That metadata can include page, slide, sheet, filename, and document information depending on the source type.

## 3. Embeddings

The production template configures the following semantic embedding
model (development and test environments use deterministic embeddings
by default):

```text
ibm-granite/granite-embedding-97m-multilingual-r2
```

Configured vector size:

```text
384
```

Embeddings are stored with provider/model metadata so they can be replaced later without reparsing every source document.

## 4. Dense retrieval

The question is embedded and compared with stored document vectors through
pgvector. The query is constrained to the already validated, user-owned
document scope.

Dense search is useful when the question and the source mean the same thing but use different wording.

## 5. Lexical retrieval

PostgreSQL full-text search runs alongside dense retrieval and uses the same
validated document scope.

Lexical search is useful for exact terms such as:

- names;
- identifiers;
- verification codes;
- product terms;
- uncommon words.

## 6. RRF

The dense and lexical rankings are combined with Reciprocal Rank Fusion.

RRF uses rank positions rather than trying to directly compare two different score systems.

## 7. Optional stages

The codebase also contains query rewriting and reranking layers.

They are disabled in the current configuration:

```text
RAG_QUERY_REWRITE_ENABLED=false
RAG_RERANKER_ENABLED=false
```

They can be tested independently without changing the default retrieval path.
The query rewriter rejects unsupported changes to identifiers, numbers,
negation/exclusion intent and exact quoted phrases (including Bangla and
Japanese negation) instead of quietly retrieving evidence for a reversed
question. Such rejections fall back to the original query.

## 8. Evidence building

Retrieved chunks are filtered, deduplicated, and limited before they are given to the model.

For Knowledge answers, the evidence packer also uses a bounded
**balanced-source budget**. When the context can afford at least 32
content tokens per planned source, it reserves space for later source
headers and divides the available text budget across the selected
ranked chunks. Otherwise it keeps the existing relevance-first greedy
allocation. This improves multi-document coverage under tight token
budgets without changing tenant filters, retrieval scores, source order
or citation IDs. The standalone context builder retains legacy
allocation unless `balance_source_budget=True` is requested.

This is a token-budget heuristic, not a claim that every additional
source is relevant or that model accuracy is proven. Compare grounded
answer quality and citation accuracy before a production rollout.

Each evidence block gets a stable label:

```text
[S1]
[S2]
[S3]
```

Those labels are later used by the citation checks.

## 9. Generation

The LLM receives the evidence and instructions to answer from that evidence.

This is different from Converse, where the model is allowed to answer more generally.

## 10. Citation validation

The generated answer is checked for citation problems such as:

- malformed references;
- citations to source IDs that do not exist;
- missing citations;
- material claims that are not cited when citations are required.

Citation formatting is normalized before the final validation.

## 11. Grounding check

A valid citation label is not enough.

The system also checks whether the cited evidence supports the claim that was made.

This matters for claims involving:

```text
names
numbers
dates
conditions
comparisons
negation
certainty
scope
```

If the answer is not supported, Aqlyra can try to repair it.

If the repaired answer still is not supported, Knowledge mode refuses instead of returning an unsupported result.

## 12. Provider failures

Provider failures are handled separately from grounding failures.

```text
unsupported claim
    -> repair / refusal

timeout / 429 / provider network error
    -> service unavailable

malformed provider response
    -> upstream response failure
```

This makes it possible to tell the difference between a bad answer and a broken provider call.

## 13. Evaluation

The test suite includes coverage for:

- dense retrieval;
- lexical retrieval;
- hybrid retrieval;
- RRF;
- query rewrite experiments;
- reranking experiments;
- citation validation;
- semantic grounding.

The current defaults are based on those tests and experiments.

## Debugging checklist

When a Knowledge answer looks wrong:

```text
1. Was the correct content parsed?
2. Did the authenticated conversation resolve the intended document scope?
3. Was it chunked correctly?
4. Did retrieval find it?
5. Did evidence selection keep it?
6. Did the model use it?
7. Were the citations valid?
8. Did the cited evidence support the claim?
9. Did the provider fail?
```
