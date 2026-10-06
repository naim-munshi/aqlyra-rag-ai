# Aqlyra Cross-Channel Evidence Benchmark v0.1

Status: pilot specification
Purpose: test the provisional cross-channel evidence-contract hypothesis without assuming a positive result.

## 1. Research objective

Measure whether exposing the same source document through different Aqlyra evidence contracts changes:

- factual correctness;
- unsupported source-dependent claims;
- evidence-supported claim ratio;
- source attribution;
- abstention behavior;
- answer completeness;
- latency and token cost.

## 2. Conditions

### K — Knowledge

- Backend mode: `knowledge`
- Same benchmark document is placed in the authorized Knowledge scope.
- The system uses its normal retrieval and grounded-answer path.
- Citations and grounding/refusal behavior are part of the condition.

### C — Converse attachment

- Backend mode: `normal` (UI label: Converse)
- The exact same benchmark document is attached to the turn.
- The system uses its normal attachment-context path.
- Strict Knowledge citation/refusal enforcement is not applied.

### N — Converse without attachment

- Backend mode: `normal`
- No benchmark document is attached.
- Purpose: measure model-only/conversational baseline behavior.

## 3. Benchmark corpus

Pilot target: 24 immutable public/synthetic documents.

Strata:

- 6 short factual documents;
- 6 long-context documents;
- 6 multi-hop documents;
- 6 distractor/conflict documents.

Do not use Aqlyra production user documents, personal CVs, test fixtures, or private files in the publication benchmark.

Each document needs:

- `document_id`
- `document_version`
- stable content hash
- source license/provenance
- page/unit boundaries

## 4. Questions

Pilot target: 120 canonical questions, five per document.

For each document:

1. direct answerable;
2. multi-hop answerable;
3. unanswerable;
4. distractor-heavy;
5. conflict/temporal.

Every question requires gold evidence annotations.

Question record fields are defined in `aqlyra_benchmark_schema_v0.1.csv`.

## 5. Expected actions

Allowed labels:

- `answer`
- `abstain`
- `answer_with_conflict`
- `answer_with_temporal_resolution`

Unanswerable questions must have no valid supporting evidence in the supplied benchmark source.

Conflict questions must include an explicit gold resolution rule, such as latest-version or authoritative-source precedence.

## 6. Pairing

The same canonical `(document_id, question_id)` pair is evaluated under K, C, and N.

Do not rewrite the question for individual conditions.

Internal retrieval rewrites are logged separately and are not part of the canonical question.

## 7. Leakage controls

Questions must not reveal:

- document IDs;
- filenames;
- gold evidence unit IDs;
- source labels;
- condition names;
- expected answers;
- citation syntax such as `[S1]`.

Gold annotations must never be placed into the model input.

## 8. Evaluation

### Retrieval layer

Knowledge only:

- Recall@k;
- evidence recall@k;
- MRR/nDCG where graded relevance is available;
- gold evidence coverage;
- distractor exposure.

### Answer layer

All conditions:

- answer correctness;
- claim completeness;
- unsupported-claim rate;
- contradiction rate;
- abstention accuracy.

### Attribution layer

Knowledge:

- citation precision;
- citation recall;
- citation completeness;
- evidence-span support.

Converse:

- evaluate whether source-dependent claims are actually supported by the supplied attachment;
- do not treat lack of citations as a failure because citations are intentionally disabled.

## 9. Claim-level annotation

Decompose generated answers into atomic factual claims.

Each claim gets:

- `claim_supported`
- `supporting_unit_ids`
- `claim_entails_gold`
- `unsupported`
- `contradicted`
- `not_applicable`

Primary unsupported-claim rate:

`unsupported factual claims / total factual claims`

Primary support ratio:

`supported factual claims / total factual claims`

## 10. Primary hypotheses

### H1 — behavioral difference

K and C will show a measurable difference in source-supported answer behavior for identical source/question pairs.

### H2 — attribution difference

K will produce more explicit source attribution because citation validation is part of the Knowledge contract.

### H3 — unsupported source-dependent claims

The unsupported source-dependent claim rate will differ between K and C.

### H4 — abstention behavior

K and C will differ on unanswerable questions because the Knowledge pipeline contains a strict grounded-answer/refusal mechanism and Converse does not.

All four are falsifiable hypotheses.

## 11. Confound controls

Keep constant where technically possible:

- source document;
- canonical question;
- user identity and authorization scope;
- LLM provider;
- model;
- generation configuration;
- evaluator model/version;
- benchmark document version;
- experiment timestamp window;
- randomization/seeding policy.

Record all configuration versions.

## 12. Repetitions

If generation is stochastic, use at least five independent repetitions per condition for the pilot.

If deterministic generation is used, perform independent repeatability runs and record the exact deterministic configuration.

## 13. Statistical analysis

Primary unit: paired question.

Primary contrasts:

- K vs C;
- C vs N;
- K vs N.

Binary outcomes:
- McNemar's test for paired binary outcomes.

Continuous per-question measures:
- choose a paired test appropriate to the observed distribution;
- report effect size and confidence interval.

Limit exploratory multiplicity; apply an appropriate multiple-comparison procedure when many secondary outcomes are tested.

## 14. Ablations

A1. Knowledge without the strict answer/refusal gate.

A2. Converse with a post-hoc citation/source evaluator but unchanged generation.

A3. Converse with context budget matched to an evidence budget comparable to Knowledge.

A4. Knowledge with gold evidence injected to separate retrieval failure from downstream generation/grounding failure.

A5. Knowledge top-k sweep.

## 15. Failure taxonomy

Primary label:

- `retrieval_miss`
- `retrieval_partial`
- `distractor_selection`
- `context_truncation`
- `unsupported_generation`
- `contradiction_failure`
- `abstention_failure`
- `citation_missing`
- `citation_incorrect`
- `answer_incomplete`
- `question_ambiguity`
- `evaluation_uncertain`

Secondary labels may be added.

## 16. Reproducibility package

Preserve:

- benchmark documents;
- question file;
- gold evidence annotations;
- exact benchmark version;
- Aqlyra commit hash;
- provider/model identifiers;
- embedding provider/model/version;
- retrieval settings;
- prompt versions;
- experiment configuration;
- raw outputs;
- claim annotations;
- evaluator outputs;
- seeds where applicable;
- timestamps;
- aggregated metrics.

Raw outputs must be append-only; do not overwrite previous runs.

## 17. Pilot acceptance gate

The pilot can scale only when:

1. every question references a valid document;
2. answerable questions have valid gold evidence;
3. unanswerable questions lack supporting evidence;
4. conflict cases have explicit resolution rules;
5. K and C use identical canonical source/question pairs;
6. no personal/private source enters the benchmark;
7. evaluators can reliably classify support/unsupported claims on a reviewed subset;
8. the system logs enough information to reproduce every condition.

## 18. Research-integrity rule

This benchmark is an instrument for testing the hypothesis. It is not evidence of novelty.

Do not claim “first,” “novel,” “state of the art,” “better,” “safer,” or causal superiority from the pilot unless those claims are supported by the completed literature review and appropriate statistical analysis.
