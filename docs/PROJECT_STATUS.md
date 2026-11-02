# Project status and evidence

[Project overview](../README.md) · [Documentation](README.md)

## Source and deployment are separate

The default branch was reviewed at `6bd16d5f42bbb75989d7590ac7b33f7ae4e2f884` on 31 October 2026. This documentation cleanup builds on that source baseline.

The [hosted application](https://aqlyra-ai.vercel.app) is developed through release branches. Features described in a release pull request should not be assumed to exist on `main`, and a passing candidate build should not be described as deployed.

The [integration candidate, PR #58](https://github.com/naim-munshi/aqlyra-rag-ai/pull/58), records consolidation of newer frontend, Core and RAG changes. At review time it remained open and described additional release gates. Its deployment notes reported separate backend and frontend commits. These are maintainer-recorded results, not a new live verification performed by this documentation review.

## What a reviewer can verify

| Evidence | What it supports | What it does not establish |
|---|---|---|
| [Backend tests](../backend/tests) | Defined regression cases and expected behaviour | Real-provider or production acceptance |
| [CI workflows](../.github/workflows) | Reproducible build and test procedures | Success without checking the relevant commit's run |
| [Retrieval baseline](../backend/evaluation/BASELINE.md) | Controlled ranking experiments | Production semantic quality or general accuracy |
| [Scripted demo](VERCEL_PORTFOLIO_DEMO.md) | Interface and interaction design | Backend calls or live AI inference |
| [Operational scripts](../scripts/ops) | Backup, restore and readiness implementation | An independently verified production restore |

## Current evaluation boundaries

- Local defaults use deterministic LLM and embedding providers.
- Genuine semantic retrieval requires a configured, available embedding provider. Release notes reported a provider-quota issue and lexical fallback; current provider health must be checked separately.
- Google sign-in, email delivery and voice require their external services. Source support does not imply live end-to-end acceptance.
- Production multi-user isolation, provider-backed document Q&A, recovery and load behaviour require dedicated acceptance evidence.
- Query rewriting and LLM reranking are feature-gated on the default-branch baseline.

Use [Staging](STAGING.md) for the acceptance procedure. Keep historical measurements and rollout records attached to their original commits rather than replacing them with unqualified test counts or readiness claims.
