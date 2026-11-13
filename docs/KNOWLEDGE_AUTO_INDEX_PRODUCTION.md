# Aqlyra Knowledge production beta — K1 / K2

## Operation

The **existing** Core API, PostgreSQL and private Neon S3 are reused. No
destructive migrations or new pages are needed.

When `KNOWLEDGE_AUTO_INDEX_ENABLED=true`, a successfully verified private
cloud PDF/DOCX/XLSX/PPTX/TXT/MD/CSV is committed as `queued` in the
existing `documents` table. Images stay `uploaded` for Converse vision.
A FastAPI worker claims at most one queued document at a time with PostgreSQL
`FOR UPDATE SKIP LOCKED`, reads the object under its DB owner using the
verified byte length, SHA256 and file signature, parses/chunks it, indexes
available embeddings and commits `ready`. A failure commits `failed` and
preserves the original S3 object. The owner can use the authenticated
`POST /documents/{document_id}/retry-index` endpoint to requeue an uploaded
or failed knowledge document. Jobs survive service restart; records left
`processing` longer than 30 minutes are requeued and reconsidered.

## Explicit feature flags

- `KNOWLEDGE_AUTO_INDEX_ENABLED=false` default; enable only after database
  readiness and production deploy health.
- `KNOWLEDGE_LEXICAL_FALLBACK_ENABLED=false` default. When true, provider
  failures or deterministic test embeddings cannot silently present
  fabricated semantic evidence. The parser's **real, owner-scoped** chunks
  remain indexable by PostgreSQL full-text search. Answer generation still
  passes through existing grounded-citation validation, and no source means
  a refusal.
- `KNOWLEDGE_INDEX_POLL_SECONDS=8` default, bounded 2–120.
- `AQLYRA_KNOWLEDGE_PROVIDER_PROBE_ON_BOOT=true` is **one-shot only**.
  It checks the configured real embedding provider, or explicitly reports
  lexical-only mode when configured for deterministic embeddings, then runs
  a synthetic prompt through the actual LLM. Turn this off after recording
  a PASS/FAIL. No user files are accessed by the probe.

## UX

Documents automatically refresh while queued/processing. Converse waits
briefly for newly uploaded documents, then truthfully explains that indexing
continues in the background. On `ready`, chat attaches the source and the
user can ask grounded questions. A failed document can be retried without
reuploading. Direct 50 MiB uploads bypass the former proxy-only indexing
block. The Documents panel remains part of existing chat workspace.

## Production acceptance (not satisfied merely by CI)

1. Real authenticated 10-page PDF upload -> status queued -> processing -> ready.
2. Ask about a page-specific claim -> exact filename/page citation, no invented answer.
3. Refresh/relogin; verify persistence and citation still work.
4. Upload a second document and compare cited claims.
5. Force embedding provider 402/5xx in an isolated synthetic test; verify
   safe lexical mode and no unsupported semantic score.
6. Force cloud read failure and verify file stays durable and user can retry.
7. Verify a different account cannot retrieve, process, download or cite the
   first account's documents.
8. Check mobile Safari, PDF 50 MiB and Render restart behavior with
   production logs and exact deployment commit.

Caveat: an indexable image-only/scanned PDF may produce no searchable text;
OCR is still a separate feature and must not be claimed complete.

Never submit real user documents to external web search. No main merge without
owner permission.
