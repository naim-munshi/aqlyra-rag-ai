# Aqlyra RAG — Advanced Retrieval Architecture & Acceptance

> Scope: **existing** Aqlyra FastAPI/Neon PostgreSQL+pgvector. Not a new RAG
> backend, vector model, API, user database, voice stack or frontend.
> Baseline: deployed backend release `3b08802686efba96cd80e9e6fd39e65504268382`,
> 2026-11-04 JST. This report differentiates code, CI and actual production.

## 1. Source-of-truth execution flow

```text
Authenticated user (Converse / Knowledge / private project)
  -> FastAPI JWT + user identity / conversation and document ownership ACL
  -> Upload -> durable private source -> parse PDF/DOCX/TXT/etc
     -> document units -> hierarchical chunks + source labels/page ranges
     -> 384-dimensional multilingual passage embeddings
        (same model name/version; never synthetic substitute)
     -> Neon pgvector and PostgreSQL FTS/chunks
     -> document ready / failure-retry status
  -> Question -> optional bounded query rewrite (feature gate)
     -> tenant/document/ready/role filters BEFORE any ranking
     -> semantic query embedding (single request + shared connection pool)
     -> dense pgvector cosine candidates + PostgreSQL lexical candidates
     -> weighted reciprocal-rank fusion (RRF)
     -> optional semantic reranker (feature gate)
     -> budgeted, diverse evidence context + real filenames/page labels
     -> existing Groq grounded generator
     -> citation validation (+ optional grounding verifier)
     -> answer with linkable citations, or explicit insufficient evidence
```

**Contract:** `execute_chat_turn` and the existing
`answer_question` / `search_hybrid_chunks` / `search_lexical_chunks`
services remain authoritative. Do not build alternate unowned RAG agents.
Do not mix third-party web evidence with private uploaded content.

## 2. Current reliable features

- Per-user ownership and document status `ready` are SQL predicates in both
  vector retrieval and lexical retrieval. `document_ids`, `chunk_roles`
  and optional cosine `min_similarity` narrow the scope further.
- Real 384-dimensional pgvector embeddings; remote worker model name and
  vector dimension must match existing records.
- Token/citation budgets, RRF rank fusion, optional query rewriting/reranking,
  explicit extraction and source provenance metadata.
- Safe lexical fallback during semantic worker failure, **when operator's
  Knowledge lexical-fallback configuration enables it**. Query with explicit
  `min_similarity` must refuse lexical downgrade. Database rollback and
  private backup acceptance are separate concerns.

## 3. RAG-only improvements in this patch

1. **Semantic vector integrity** (ported from existing draft PR #98):
   reject malformed remote responses, strings/booleans/nulls, nonfinite/zero
   vectors, wrong model/dimension, and use numerically stable normalization;
   no new embeddings, reindex or vector schema migration.
2. **429 rate-limit recovery**: one HTTP 429 immediately opens a shared,
   bounded 10–60-second semantic-worker circuit; no unproductive immediate
   retry. Valid `Retry-After` seconds are clamped; malformed values are
   ignored. After cooldown, the worker is probed normally. This **does not
   create capacity or solve the Render edge quota**.
3. **Hybrid lexical-only evidence**: when indexing completed without an
   `EmbeddingRecord`, RRF retains a genuine lexical match rather than
   silently dropping its passage. The metadata explicitly says
   `semantic_similarity_available=false`. No fabricated cosine similarity
   is treated as valid. Any explicit `min_similarity` prevents this fallback.
4. **Retrieval metrics**: add binary NDCG@K and mean NDCG@K to existing
   Recall@K, Hit@K and MRR; deduplicate chunk IDs and preserve API-compatible
   dataclass fields.
5. **Multilingual isolated test corpus**: PostgreSQL FTS and Unicode path
   evaluation for English, বাংলা, 日本語, Banglish; 2-user document security
   test. Synthetic text only; never report its scores as live production.

## 4. Next phases, with gates

### P0 — Semantics/quality and safety (current)
- Full backend PostgreSQL 16 and 18 CI on **exact PR head**;
  vector parsing, 429 circuit, dense/lexical fusion, strict cosine boundary,
  cross-account and scoped-document tests must all pass.
- Inspect Render logs after deployment; confirm rate-limit circuit decreases
  repeat provider calls and citations continue to refer to real chunks.
- Verify no mismatch between model `bekko-static-multilingual-int8-mrl384-v1`
  and existing 384D production embeddings.

### P1 — Measurement with labeled owner-approved content
- Use separate **consented, private** EN/BN/JA/Banglish labeled queries and
  source chunks. Record per-language Recall@5, Recall@10, MRR@10,
  NDCG@10, citation accuracy, abstention precision and hallucination rate.
  Compare no-reranker baseline to opt-in reranker and query rewrite.
- Instrument read-only retrieval stage time vs generation p50/p95 and 429
  rate without logging document bodies, queries, user IDs or secret tokens.
- Evaluate chunk sizes, OCR, scanned PDF page provenance, duplicated
  sections and cross-document reasoning, with no automatic migrations.

### P2 — Enterprise access, durability, scale
- User/document ownership is **not** organization/department/HR RBAC.
  Add server-side role/classification ACLs before first source retrieval only
  after approved schema/access plan and negative shared-knowledge tests.
- Confirm private cloud object upload/read/delete/restart persistence and
  independent backup/restore with isolated test tenants.
- Test 25–100 independent users and provider-real load in **isolated staging**
  within rate/cost budgets. Existing one Free Render instance is not
  evidence of company load capacity.

## 5. Release and SKIPPED policy

- `CODE CHANGED` = PR contains implementation and regression tests.
- `CI PASS` = exact SHA, PostgreSQL version and failures listed.
- `DEPLOYED` = Render service deploy SHA and startup health verified.
- `REAL E2E VERIFIED` = authenticated actual document upload, indexing,
  source retrieval, citations, reload, and role isolation observed.
- Do not merge into protected `main`, delete branches, force push, or write
  to production user documents. Leave real user-device and provider-stress
  tests `SKIPPED/BLOCKED` with reasons until executable.
- In particular, PR #98 is the *source* of the verified vector/NDCG change,
  not another independently deployed RAG stack. Close/supersede it only
  after consolidated PR acceptance.
