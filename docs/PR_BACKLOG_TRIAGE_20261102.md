# Aqlyra pull-request hygiene audit — 2026-11-02

**Repository:** `naim-munshi/aqlyra-rag-ai`  
**Evidence:** connected GitHub open-PR listing, descriptions, bases/heads, changed-file lists, focused commit comparisons, 100 recent `main` commit subjects and selected PR commit histories. This is **backlog triage**, not a complete line-by-line code audit of all historical commits or a production acceptance certificate.

## Outcome

- Starting queue: **61 open pull requests**.
- **19 superseded/validation/snapshot pull requests closed** with a preserving explanation and the retained successor linked in the PR discussion.
- Remaining open queue: **42 PRs**. **No pull request was merged, no Git branch was deleted, no published Git commit was rewritten**, and protected `main`, production services and stored user data were unchanged by this cleanup.
- Retargeted **#101** from #100 to **#90** and consolidated the first-transcript LiveKit unmount fix, unexpected RTC disconnect guidance and centered new-chat composer into one 4-file PR. Git comparison proved all #100 commits were ancestors of #101.
- Updated PRs **#48**, **#46** and **#101** to use specific Aqlyra feature language rather than a competitor-name UI label. Open PR title/body scan found no competitor-inspired UI copy labels after the change; the word "clone" in the retained full-release PR #37 refers to a **Neon database branch clone**, not product cloning.
- Updated the existing docs PR **#81** (not a separate PR): `ENGINEERING_PRACTICES.md`, PR template and README guidance for one cohesive PR per workstream, precise commit descriptions and source-vs-live evidence.

## Closed PRs (history and branches preserved)

| Closed | Retained proposal | Verified rationale |
| --- | --- | --- |
| #100 | #101 | Exact ancestor; single frontend voice lifecycle + welcome layout candidate |
| #89, #86, #83 | #90 | Exact ancestor chain; voice/reply-language improvements retained in Voice release |
| #54 | #56 | Exact ancestor; Knowledge indexing core retained in K3 |
| #47 | #36 | Exact ancestor; web-search backend candidate retained in live Core branch |
| #26 | #33 → #35 | Exact ancestor; temporary integration validation folded into later security candidate |
| #33 | #35 | Exact ancestor; duplicate prior integration review proposal |
| #12, #14, #16, #19, #20 | #22 → #35 | Verified ancestor chain; older stacked research/office/browser steps retained in integration branch |
| #25 | #23, #24, #35 | Temporary CI-only validation snapshot; independently scoped dependency PRs and integration candidate remain open |
| #99 | #36 and closed PR record | Date-specific production-status snapshot, not a deployable feature; source branch and discussion preserved |
| #27 | #29 | Exact ancestor; original artifact code retained with additional security hardening |
| #31, #22, #11 | #35 | Exact ancestors; security/research, Study Abroad and auth features preserved in retained integration candidate |

**Note:** PR #26 was already closed directly to #33 before #33 was subsequently closed to #35. That is a verified chain, not lost source. Closed PRs may be reopened if a unique change is later found.

## Retained open PRs, grouped by actual engineering responsibility

| Workstream | Open PR numbers | Release review decision |
| --- | --- | --- |
| Core and integration | **#36, #37, #35, #32, #58** | #36 is existing Render Core branch. Others are historical or cross-system integration proposals; compare against the actual current frontend and Core before merging. |
| Conversation UX and LiveKit | **#90, #101, #40, #41, #96, #97** | #101 is currently deployed on Vercel but **not merged into protected main**; #90 remains Railway worker lineage. #96/#97 are narrow unmerged token-cache security patches. Current real voice call still auto-disconnects; do not claim LiveKit audio E2E PASS. |
| RAG, chat and knowledge | **#95, #98, #55, #56, #44** | Preserve context budgeting, vector validation and measurable retrieval evaluation. #55 is UI progress; #56 is OCR/multilingual evidence. Do not blindly merge old 200+ file snapshots. |
| Research and browser | **#46, #48, #84, #85** | Stand-alone research UI/backend work must be reconciled; keep browser external execution disabled until explicit authorization, sandbox, SSRF and provider-backed tests. |
| Authentication, security and local safety | **#7, #8, #9, #10, #23, #24, #28, #30, #38, #42, #43** | Verify patch-level differences and source version before any conclusion that old security proposals are already integrated. Do not close unverified security controls merely for a lower PR count. |
| Private artifacts, uploads, docs and history | **#21, #29, #49, #50, #51, #52, #53, #81, #82** | Owner-scoped storage and file handling remain sensitive; preserve candidate diffs and security reviews. #81 documents repository quality standards. |
| Study Abroad and independent voice/mobile fixes | **#39, #45** | #39 is a schema-compatible API candidate; #45 is an old mobile upload warning snapshot. Review actual production behavior before integrating. |

## Root cause of PR count inflation

A large fraction of older PRs target the default `main` while production uses newer, diverged **Render Core** and **Vercel Voice/UI** branches. Some supposedly small PRs then show 200–330 changed files against `main`, even where the intended change is a handful of frontend/backend files. This is a branch-ancestry and release consolidation problem, **not** evidence that every file should be merged.

Fix the topology before merging: use a correct, deployed base commit; isolate the functional diff; preserve both independent Core and Voice worker deployment boundaries; require exact-head CI and real acceptance; then consolidate into a reviewed release PR. No new service, datastore or product rewrite is needed.

## Branding and commit history

- Do not label Aqlyra features in terms of another assistant's UI, or call the product a clone. Describe its actual capability (conversation composer, grounded research, realtime voice or private document retrieval).
- Public Git commit objects are immutable content-addressed history. **Do not force-push historical release branches to scrub old wording**; update visible PR titles/descriptions and adopt the new template for future commits.
- The latest 100 commits reachable through repository commit search on `main` were inspected by subject; no competitor-style UI commit subjects were found in that sample. Selected open-PR commit histories were additionally reviewed; a **complete every-commit history audit was not performed**.
- Nothing in this audit confirms full phone microphone → LiveKit dispatch → STT → same Aqlyra AI brain → audible TTS. This has a separate live incident gate.

## Gate for future PR cleanup

Close an old PR only when its head is proven included by ancestry in a retained branch, or when it is an explicitly obsolete CI-only / dated documentation snapshot. Annotate closure with the successor. If security, storage, schema, auth, voice or browser execution differs from the live implementation, **keep the PR open for independent review** instead of guessing. Do not delete a branch referenced by another PR, a live deployment or rollback.

This audit is intentionally conservative: 42 open **does not mean 42 required production features**. A dependency-aware integration review must decide which unique changes, if any, should be merged.
