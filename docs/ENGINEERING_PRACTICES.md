# Aqlyra engineering and release practices

Aqlyra is an independent AI product with its own conversation model, retrieval, privacy, voice, research and document workflows. These rules apply to repository contributors and automation.

## Product identity and writing

- Describe the **actual Aqlyra behavior** precisely: e.g., "center the welcome composer", "inline sourced research", "persistent LiveKit room", "hybrid retrieval".
- Do not use competitor product names, "clone", "copy", "-style", "like <product>", or unsupported comparison claims in PR titles, commit subjects, public product copy, issue headings, screenshots or marketing.
- Technical citations and factual comparative analyses are exceptions when clearly labeled as references, not an identity claim. Keep design decisions grounded in user needs, accessibility, security, and observed behavior.
- Do not rewrite published Git history just to alter old wording. Correct the visible PR metadata and future commit practices. Old closed PR/commit history is an audit trail, not the current product brief.

## A coherent change, not a PR per edit

- Use **one active PR per coherent engineering workstream** (e.g., voice reliability, RAG quality, authentication, conversation UX). Add related code, regression tests, CI fixes and docs in new commits to the **same PR**.
- A small independently deployable security hotfix can justify its own narrow PR. Opening one PR per test, screenshot, status report, string or margin change normally does not.
- Use descriptive commit subjects: `fix(voice): preserve RTC room across history update` or `fix(ui): center Aqlyra's welcome composer`. Subject lines explain observed behavior, not resemblance to another app.
- Dependent PRs are exceptions when Core and Vercel/Railway have **separate deployable branches**, but document the dependency and eventual consolidation.
- Keep unfinished Browser Agent, model or schema migrations disabled until security and provider-backed acceptance. A PASS in synthetic CI is not proof of live service acceptance.

## Release, review and cleanup

1. Record **source branch and exact commit** for every intended change; map live Vercel, Render and Railway deployments separately. Never assume `main` is currently deployed.
2. Check affected behavior, authentication/tenant isolation, mobile layout, real voice call lifecycle, rate limits, database consistency and rollback where relevant.
3. Complete exact-head CI and review before release. Real provider/microphone/security E2E requires separate evidence and cannot be inferred from green workflows.
4. Rebase or retarget *stacked PRs* to the actual retained integration parent. Close a redundant PR only when its code is confirmed included by commit ancestry or the PR is explicitly an obsolete validation-only snapshot; link its retained successor in the closing note.
5. **Closing a PR is not deleting code or Git history.** Never delete branches still referenced by a live deployment, another PR or a release rollback. Do not rewrite protected `main`.
6. Do not publish credentials, session JWTs, private documents, recorded audio, personal user identifiers or account secrets in logs, review comments or screenshots.

## Preferred workstreams

- **Conversation and voice:** persistent composer and LiveKit lifecycle, real STT/AI/TTS, authorized sessions, Bangla/Japanese/English quality.
- **RAG and knowledge:** retrieval integrity, measured ranking quality, citation grounding, document processing and owner isolation.
- **Research and browser:** source relevance, approval gating, SSRF/prompt-injection protections and sandbox E2E.
- **Identity and privacy:** verified OTP/OAuth/password reset, guest restrictions, private files, backup/restore.
- **Release engineering:** exact-commit CI, deploy health, rollout verification, rollback, reliable dated documentation.

Avoid opening additional parallel PRs for small steps inside these workstreams.