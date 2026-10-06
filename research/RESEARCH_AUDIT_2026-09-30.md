# Aqlyra Research Program — Consolidated Audit

Date: 2026-09-30
Scope: Research work completed through the current `research/rq-literature-foundation` line, including RQ iterations, literature review, provenance/reproducibility checks, baseline audit, retrieval pilots, trace capability audit, and Converse/Memory architecture analysis.

## Executive conclusion

The work has successfully moved from a broad “trustworthy RAG” idea to a substantially better-defined empirical research program. The strongest parts are the systematic rejection of several over-broad or already-covered RQ candidates, the embedding provenance/reproducibility audit, the explicit separation of production engineering from research experiments, and the discovery that Aqlyra exposes the same user-provided document through two materially different evidence contracts.

The main issue is not lack of technical material. It is that the project accumulated several candidate RQs before the underlying phenomenon and benchmark were fully fixed. The next stage should therefore stop creating new RQ variants until the benchmark can demonstrate a reproducible, falsifiable effect.

## Current status by workstream

| Workstream | Status | Evidence / note |
|---|---|---|
| Research scope | Stabilized | Broad RQ churn stopped after v0.7; benchmark-first policy adopted. |
| Literature seed set | Substantial seed coverage | 28 seed records were validated in the existing matrix; this is not yet a complete systematic review. |
| Prior-art verification | Strong pilot stage | 28 seed items classified as primary-source verified in the existing verification file; exact novelty still requires continued coverage. |
| Production baseline provenance | Verified | Current production corpus audited; historical Granite vectors reproduced from the recorded model/path. |
| Embedding reproducibility | Passed | 401/401 Granite vectors reproduced; minimum cosine 1.0, max absolute difference about 2.04e-7, so “reproduced” rather than “bit-identical.” |
| Retrieval implementation audit | Passed | User scope, document readiness, provider/model/dimension compatibility, hybrid retrieval and RRF behavior inspected. |
| Authorization/embedding pilot | Engineering invariant established | Hybrid lexical rescue depends on compatible embedding coverage; pilot was intentionally synthetic and is not publication evidence. |
| Trace capability audit | Completed | Retrieval, authorization, pruning, truncation, citations and grounding are partially observable; full per-source disappearance lineage is not currently exposed. |
| Converse/Memory architecture audit | Completed | Memory and attachment contracts are now explicit; Knowledge and Converse are separate product flows. |
| Benchmark design | Ready to implement | Controlled K/C/N design specified below. |
| Statistical plan | Specified | Paired comparisons; McNemar for binary outcomes; effect sizes/CI for continuous outcomes. |
| Publication claim | Not ready | No “novel”, “first”, “SOTA”, or causal claim should be made yet. |

## 1. Research-question evolution review

### v0.1–v0.2: broad trustworthy-RAG framing

Useful as a starting point, but too broad for a research paper because “trustworthy RAG” spans retrieval quality, grounding, citation correctness, authorization, robustness, and abstention.

Decision: superseded.

### v0.3: authorization/evidence sufficiency

Important system property, but the literature already contains permission-aware and authorization-first RAG work. The concept therefore should not be presented as a standalone novelty claim.

Decision: retained as background/engineering capability, not the main RQ.

### v0.4: paired full-vs-restricted authorization + claim provenance

Methodologically stronger, but still close to current work on permission-aware retrieval, authorization-limited evidence, evidence sufficiency, and controlled paired interventions.

Decision: candidate rejected as a novelty claim.

### v0.5: authorization selectivity × query correlation × hybrid retrieval × adaptive retrieval

Technically interesting, but the filtered-vector-search and predicate-aware retrieval literature is already mature enough that the combination needs a much more specific scientific contribution than the current framing provided.

Decision: candidate rejected/held.

### v0.6: causal stage-wise attribution

This moved toward intervention and failure attribution, which is scientifically stronger. However, recent RAG diagnosis and interventional failure-attribution work substantially overlap with the idea.

Decision: candidate rejected/held.

### v0.7: embedding-index heterogeneity as an authorization-aware RAG confound

The engineering audit demonstrated a real system interaction: compatible provider/model/dimension coverage matters to hybrid retrieval. However, the current pilot was mostly constructed by manipulating embedding metadata and therefore cannot support a paper-level causal claim. Reproducibility and embedding heterogeneity are also increasingly studied independently.

Decision: retain as a confound/control variable, not the headline RQ.

## 2. Baseline and reproducibility review

The production corpus currently contains 55 documents, 517 chunks, and 517 embedding records. It contains 401 historical Granite vectors and 116 deterministic vectors. The active production retrieval path filters by provider/model/dimension, so the mixed historical vector records are primarily provenance/configuration history rather than evidence of an active cross-provider ranking bug.

The Granite reproducibility audit is one of the strongest completed research artifacts. The current Hugging Face inference path reproduced all 401 stored vectors. Because the largest observed absolute difference was approximately 2.04e-7 rather than exact binary equality, the correct wording is “numerically reproduced within tolerance,” not “bit-identical.”

The certificate/TLS investigation was handled correctly by preserving certificate verification and using a trusted network path instead of bypassing TLS. No insecure `verify=False` or `curl -k` style workaround should enter the research protocol.

## 3. Retrieval pilot review

The authorized embedding-coverage pilot produced:

- 100% compatible coverage → 100% hybrid target retention
- 75% compatible coverage → 75% hybrid target retention
- 50% compatible coverage → 50% hybrid target retention
- 25% compatible coverage → 25% hybrid target retention
- 0% compatible coverage → 0% hybrid target retention

This result demonstrates a current implementation dependency: lexical candidate recovery is not enough when the hybrid service requires a compatible embedding record before a lexical-only candidate can survive into the final result.

However, because the pilot deliberately changed provider metadata on selected records, these measurements are diagnostic of the implementation and should not be reported as a discovered real-world law.

## 4. Converse and Memory architecture review

### Converse (backend `normal`)

Converse receives recent conversation history and, when enabled, user-scoped personal memory. Memory retrieval returns `kind` and `content`; the underlying Memory record also stores `source_message_id`, but that source identifier is not included in `MemoryRetrievalHit` and therefore is not passed to the normal LLM generation context.

The Converse prompt explicitly treats personal memory as context rather than document evidence and explicitly prohibits invented document citations.

### Knowledge (backend `knowledge`)

Knowledge resolves follow-up references using Knowledge-mode history, retrieves authorized document evidence, and uses the grounded answer pipeline with citation/grounding semantics.

The Knowledge contextualizer deliberately treats conversation history as untrusted context used to form a retrieval question, not as factual evidence.

### Normal attachment path

The same underlying user-owned document can enter Converse through `DocumentUnit` context loading. The attachment path intentionally bypasses strict Knowledge/RAG refusal and citation enforcement.

This is a product-contract difference, not automatically a defect.

### Memory extraction

Automatic memory extraction operates on the persisted user message. It explicitly excludes assistant-generated information, document/RAG evidence, and source citations. Therefore a Knowledge assistant answer does not automatically become a persistent memory item through the current extraction contract.

### Mode switching

The frontend product flow maintains separate `normalConversationId` and `knowledgeConversationId` state and clears the current turns when the UI switches between Converse and Knowledge. Backend mode mutation exists through `ConversationUpdate.mode`, but the normal product UI flow does not use a same-history mode switch.

Therefore the previous “Knowledge answer crosses into the same conversation after a UI mode switch” hypothesis should not be used as the main research setup.

## 5. Literature-review conclusions

The current literature makes several candidate claims unsafe as novelty statements:

- multi-turn RAG by itself is established;
- conversation-history versus retrieved-evidence separation is already explicitly studied;
- joint conversational-memory + long-document reasoning is already benchmarked;
- provenance-aware long-term memory is actively developed;
- context–memory conflicts have controlled benchmarks;
- document/source attribution in RAG is already an explicit research area.

Representative verified sources include 5ting (SemEval-2026 Task 8), Comprehensive Comparison of RAG Methods Across Multi-Domain Conversational QA (EACL 2026 SRW), MemoryDocDataSet (2026), Task Matters (Findings ACL 2026), MemORAI (Findings ACL 2026), SEEM (ACL 2026), Agent Zero Memory (2026 preprint), and Source Attribution in RAG (2025 preprint).

This means the novelty burden has shifted from inventing another RAG/memory component to identifying a narrowly defined, reproducible phenomenon that is not already covered by these settings.

## 6. Current research hypothesis

The current defensible hypothesis is:

> Exposing the same source document through materially different evidence contracts can change factual correctness, unsupported-claim behavior, attribution, and abstention behavior even when the underlying source, question, model, and user authorization are held constant.

This is a hypothesis, not a conclusion.

## 7. Why the benchmark must be paired

Every canonical question should be evaluated using the same source/question pair under:

- K: Knowledge / strict RAG
- C: Converse / attachment
- N: Converse / no attachment control

The pair structure is essential because document choice, question difficulty, and model differences must not become confounders.

## 8. What must happen before RQ-v1.0

RQ-v1.0 should be locked only after all of the following are demonstrated:

1. the benchmark has answerable, unanswerable, multi-hop, distractor, and conflict cases;
2. the same document/question pair is actually used in K and C;
3. evaluators can reliably distinguish supported from unsupported claims;
4. the main comparison produces a measurable effect or a meaningful null result;
5. the effect survives the main controls and at least one relevant ablation;
6. the exact literature search has been updated through the benchmark design date.

## 9. What should not be done next

Do not add more features to Aqlyra for the sake of the paper.

Do not alter the production retrieval architecture merely to make the hypothesis succeed.

Do not treat the existing 55-document production corpus as the publication benchmark.

Do not convert implementation observations into causal claims without intervention.

Do not use LLM-as-judge as the only evaluator for factual correctness.

Do not call a result “novel” until the final literature matrix has been re-checked against the exact final formulation.

## 10. Recommended immediate deliverables

1. Build the controlled benchmark described in `aqlyra_benchmark_spec_v0.1.md`.
2. Implement a small gold-annotated pilot before scaling.
3. Add experiment logging without modifying the production branch.
4. Run K/C/N on the identical paired items.
5. Perform the failure analysis before changing the research question.
