# Aqlyra engineering audit — 2026-11-08

## Scope and immutable revisions

- Canonical `main` audited at `6bd16d5f42bbb75989d7590ac7b33f7ae4e2f884` (pre-production reference).
- Separately audited active backend release `release/core-without-study-abroad-20261027` at `e3f598a0ab1e5cded18359fd499541ea60192350`.
- **Do not treat `main` as the currently deployed backend.** The Render service is configured to build the release branch, and release/production acceptance varies by capability.
- Sources: immutable GitHub tree and source reads, GitHub Actions run logs, checked-in evaluation corpus, and the public security advisories listed below. Read-only audit performed before changes.
- No production database, secret, user data, deployment, or voice service was modified.

## Execution paths verified by inspection

**Knowledge ingestion:** `api/documents.py` → `services/document_processing_service.process_document` → `parsers/` → `services/chunk_service.create_document_chunks` → `services/embedding_service.create_chunk_embeddings` → PostgreSQL `DocumentChunk` and `EmbeddingRecord`, with provider/model/dimension/content metadata. The release adds queued indexing (`services/knowledge_index_queue.py`) and semantic backfill.

**Knowledge answer:** `api/rag.py` → `services/rag_answer_service.answer_question` → optional query rewriting → `services/hybrid_retrieval_service.search_hybrid_chunks` → `search_similar_chunks` + `search_lexical_chunks` → reciprocal rank fusion → optional reranking → context/token budget → `rag/answer_service.py` → `rag/citation_validator.py` → optional `rag/grounding_verifier.py` → answer/repair/refuse.

**Access boundary:** Authentication is required by `api/rag.py` and `api/retrieval.py`. Dense and lexical queries join to `Document.user_id == query.user_id`, require ready documents and retain explicit document-ID restrictions. These source-level controls also have owner-isolation tests; CI tests are not a substitute for adversarial real-user pentesting.

## A: Dependency security — CONFIRMED on `main` (P0/P1)

**Observed:** GitHub Actions `41445567100` (2026-11-02, `main@6bd16d5f`) failed both production npm audit and Python pip-audit. The earlier `40305728837` also failed. This is a reproducible *pinned dependency inventory* issue, not merely a failed test job.

| Lock/pin on main | Audited advisory | Smallest selected mitigation |
| --- | --- | --- |
| `next@16.4.0` and matching SWC/linter lock graph | GHSA-2464-fhr4-w9xw, GHSA-p3m5-59mp-jv5r, GHSA-673q-mjm6-r5xr | `next@16.4.3` and matching exactly-locked Next packages |
| `langgraph@1.2.10`, `langgraph-sdk@0.4.4` | CVE-2026-118667 / GHSA-3fx2-cqw9-xr3c | `1.2.14`, `0.4.6` |
| `pillow@12.3.0` | Multiple 2026 image-processing advisories identified by pip-audit | `13.0.0`; remove duplicate `Pillow==12.3.0` pin |
| `pyasn1@0.6.4` | CVE-2026-119194 and related advisories | `0.6.5` |
| `pypdf@6.19.0` | Multiple 2026 PDF parsing advisories | `6.21.4` |
| `certifi@2026.7.22` | PYSEC-2026-4320; confirmed in exact-head rerun | `2026.10.23` |
| `aiohttp@3.14.3` | CVE-2026-111064 and related; observed on exact-head PR pip-audit | `3.14.4` |
| `dnspython@2.8.0` | CVE-2026-114605; observed on exact-head PR pip-audit | `2.9.0` |
| `filelock@3.32.0` | CVE-2026-112940 and related; observed on exact-head PR pip-audit | `4.2.1` |
| `yarl@1.24.5` | Confirmed resolution conflict: `aiohttp 3.14.4` requires `yarl>=1.25.1` | `1.25.1` |

The above selected versions already passed a dependency audit on the *later release* branch (2026-11-07 workflow `42387740063`). This is compatibility evidence, **not proof of the new `main` PR passing**; the new PR must run npm ci, npm audit, pip-audit, backend tests and frontend build.

**Reachability:** Next is the web application's framework; its image optimization endpoint is framework-controlled, and exact exposure needs runtime review. The Server Actions and `use cache` advisories are conditional on the matching features. Pillow/PDF parsing occurs in the document ingestion surface and thus merits immediate patching. The LangGraph SDK v3 identifier interpolation issue is conditional; a direct untrusted v3 streaming call path has not been demonstrated. Pinned vulnerable packages are remediated without claiming every exploit precondition was established.

**Files changed by this PR:** `backend/requirements.txt` (nine advisory pins plus required compatible `yarl`), `frontend/package.json`, `frontend/package-lock.json` (twelve Next/SWC/linter entries only), and `scripts/ops/test_security_advisory_pins.py` (standard-library regression test). No `npm audit fix --force`, wide dependency upgrade, suppression, or production configuration change.

## B: Semantic embedding HTTP 429 — EXTERNAL PROVIDER ISSUE; mitigation ALREADY IMPLEMENTED on release

- `main` has Hugging Face/OpenAI/deterministic embedding adapters; it **does not** contain release's `remote_semantic_provider.py`.
- On release, `RemoteSemanticEmbeddingProvider._embed` explicitly handles a 429 without retrying, bounds `Retry-After` cooldown (10–60 seconds), uses a shared process-local circuit, pools HTTP clients, rejects unsafe endpoints and validates all 384-vector outputs.
- `backend/tests/test_remote_semantic_resilience.py` reproduces 429s **with httpx mocks**; it proves classification/cooldown logic, **not production provider uptime**.
- `services/rag_answer_service._retrieve_rag_hits` permits a feature-gated lexical-only fallback on embedding error; `_lexical_evidence_fallback` uses owner-scoped real lexical passages, keeps semantic scores unavailable and refuses downgrade when `min_similarity` is required. Retrieval ranking, citations and grounding must not label lexical fallback as successful dense retrieval.
- Release indexing `services/document_processing_service.process_document` may mark successfully parsed and **lexically searchable** documents `ready` after remote embedding failure; chunk metadata explicitly says `retrieval_mode=lexical_only`. Whether the frontend clearly exposes the missing dense index needs user-facing acceptance. No indexing-status schema/data changes were attempted here.
- Exact provider quota and transient 429 incidence **not reproduced during this audit**: no independent authorized test credential or dedicated live staging workload available. Quota cannot be repaired by code alone.

## C: Evaluation quality — PARTIALLY IMPLEMENTED; real-provider validation MISSING

- Corpus: `backend/evaluation/corpus/` contains 10 synthetic documents; `retrieval_cases.json` contains 20 annotated questions. Original documented experiment indexed 70 chunks.
- `backend/app/retrieval/benchmark.py` and `backend/app/retrieval/evaluation.py` compute Hit Rate@K, Recall@K and MRR@K with unique document-chunk rankings. Main's evaluator does not yet expose Precision@K or nDCG@K; the later release adds binary nDCG.
- `backend/evaluation/BASELINE.md` explicitly labels SHA-256 deterministic embeddings **non-semantic**. The supplied vector-vs-hybrid and Groq query rewrite/rerank numbers are historical measurements on this limited synthetic corpus, **not semantic embedding accuracy**.
- Rewriting and reranking are optional and feature-gated. Their individual effect, six-combination ablation, runtime latency, cost, citation correctness, grounded-answer accuracy and unsupported-answer refusal need a controlled labeled repeatable experiment with true semantic embeddings and independent answer labels.
- Tests of the benchmark and grounding include fake providers/mocks. No new real provider accuracy, semantic recall, or production throughput numbers are asserted by this PR.
- Reproducible future protocol: freeze corpus/questions/relevance judgments and SHA; fixed seed and embedding model/version; separate private synthetic tenant/DB; run dense, lexical, hybrid, hybrid+rerank, hybrid+rewrite, hybrid+rewrite+rerank at K=1,3,5 with independent repeated runs. Report macro Precision@K, Recall@K, MRR, binary nDCG@K, Hit Rate, p50/p95 retrieval/answer latency, token usage and model cost. Grade answer grounding and citations against *human-labeled* supports, independently from retrieval judgment. Refusal denominator must include actually unanswerable queries. Store redacted machine-readable results and variance; label deterministic vs provider-backed clearly.

## Additional verified CI issue on release

On 2026-11-07 (`e3f598a0`), `42387740011` (Merge Gate) and `42387740039` (Deployment Checks) failed. Root cause: their standard-library `unittest discover` stage imports `scripts/ops/test_ephemeral_chat_load.py`, which imports `pytest`, but these lightweight jobs install no `pytest`. Trace ends in `ModuleNotFoundError: No module named 'pytest'`. Backend tests, pinned production npm/Python dependency audits, native ARM64 and security-static checks succeeded. This is a **confirmed runner/test-dependency incompatibility**, separate from production application reliability. A separate focused release-branch fix is required; do not suppress or skip these jobs.

## Portfolio claims and evidence boundaries

**Verified in code and CI:** owner-scoped SQL retrieval, deterministic RAG pipeline and citation/refusal tests, synthetic 10–100 request FastAPI load, bounded 429/circuit behavior in mocked tests, pinned dependency audits on the release, platform deployment contracts.

**Not verified as product-quality results:** production concurrency with Groq; production semantic provider availability; real multilingual semantic retrieval benchmarks; independently graded grounded answer accuracy; fully accepted real LiveKit user voice sessions; external tenant pen test; end-to-end backup recovery on the hosted production topology.

The isolated 0.15-CPU/512-MiB synthetic Docker result (GitHub Actions `42387165561`) achieved 100/100 successful deterministic calls but missed the illustrative p95 target at 100 simultaneous calls (p95 10.35 s). **Do not** present that as 100 real-user Groq capacity.

## Priorities after review

1. Merge only reviewed, green security PR changes into canonical main through normal governance.
2. Correct the confirmed release unittest-import CI failure in a separate PR; restore an all-green release gate.
3. Verify real 429 in an isolated provider staging account and inspect whether lexical degradation is clearly visible in every UI.
4. Build answer-level human-labeled and real 384D embedding evaluation with six retriever variants and reproducible metrics.
5. Reconcile stale main vs release lineage without force merges, data migrations or production deploy side effects.

**No changes to production secrets, database records or live deployments were made by this audit.**
