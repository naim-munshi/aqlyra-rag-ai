# Pilot Study v0.1

Date: 2026-09-29
Status: PRE-REGISTRATION DRAFT / NOT A FINAL EXPERIMENT

## Objective

Test whether embedding-index provenance changes the measured effect of
authorization restriction in a controlled RAG setting.

## Research Factors

### Factor A: Index provenance

A1:
100% Encoder A

A2:
100% Encoder B

A3:
Mixed Encoder A + Encoder B

The mixed condition must be constructed by controlled assignment rather than
by random production history.

### Factor B: Authorization

B1:
Full corpus visible to the requester.

B2:
Restricted corpus visible to the requester.

The underlying global corpus remains identical.

## Controlled Variables

- question set
- document contents
- ground-truth supporting documents
- ACL assignments
- query wording
- query encoder where applicable
- retrieval algorithm
- top-k
- RRF parameter
- generator
- decoding configuration
- evaluation protocol

## Primary Retrieval Measures

- Recall@1
- Recall@3
- Recall@5
- MRR
- nDCG@k

## Authorization-Aware Retrieval Measures

- authorized evidence recall
- unauthorized retrieval count
- unauthorized exposure count
- evidence sufficiency rate

## Downstream Measures

- supported-answer rate
- unsupported-answer rate
- appropriate abstention
- citation support

## Primary Analysis

Estimate the effect of:

1. index provenance,
2. authorization restriction,
3. provenance × authorization interaction.

The interaction is the main pilot quantity.

## Required Controls

The pilot must include:

- at least one condition where all relevant support is authorized;
- at least one condition where material support exists globally but is
  unauthorized;
- at least one condition where no sufficient support exists globally;
- at least one multi-document question requiring more than one supporting
  document.

## Important Design Rule

The mixed index must not be treated as a valid semantic index by assumption.

Its purpose is to quantify the retrieval consequences of provenance
heterogeneity.

Therefore a matched single-encoder index is always required as a control.

## Success Criterion for Continuing

Continue to full benchmark design only if:

1. the pilot is technically reproducible;
2. authorization and embedding effects are empirically separable;
3. the interaction produces a non-trivial effect worth investigating;
4. the observed effect is not fully explained by a simpler known failure mode;
5. the literature gate remains open after inspecting the closest prior work.

No novelty conclusion is made from the pilot alone.
