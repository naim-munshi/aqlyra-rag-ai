## Aqlyra change objective

Describe the user-observed defect or independently valuable capability. Use **Aqlyra-native** names, not another product's branding or "-style" wording.

## Scope and dependency

- Workstream:
- Based on branch and exact commit:
- Existing production services affected:
- Supersedes or depends on existing PRs:
- Is this a necessary independent PR, or should it be a commit on an existing workstream PR?

## Evidence and verification

- [ ] Observed behavior and root cause described
- [ ] Focused code and automated regressions included
- [ ] Exact-head CI verified (jobs and commit SHA)
- [ ] Auth, tenant isolation, rate limits and data safety reviewed where applicable
- [ ] Real provider/device E2E separately marked PASS, FAIL or BLOCKED (no mock-only PASS)
- [ ] Deployment and rollback evidence recorded if live
- [ ] No protected-main rewrite, unreviewed destructive migration or exposed secrets
- [ ] PR and commit wording describes **Aqlyra's actual behavior**, not an imitation or superficial comparison

## Release status

- Source-only / Preview / Production / Blocked:
- Vercel/Render/Railway deployment ID, if applicable:
- Unverified conditions and owner-only actions:
