# GitHub main branch ruleset - owner setup and verification

Last direct ruleset inspection (2026-11-27) found an active ruleset:
`aqlyra-main-production-gate` (ID `25905480`), targeting the default branch,
with 11 required job contexts plus deletion and non-fast-forward restrictions.
However, its required approving review count is **0**; last-push approval and
code-owner review are also disabled. Therefore the ruleset is active but does
**not** enforce the independent review required by this release policy.
The GitHub connector cannot update Rulesets; a repository administrator must
change this setting. Do not confuse an active ruleset or green CI with a
complete release protection gate.

## Owner action - complete the existing enforced ruleset

Open https://github.com/naim-munshi/aqlyra-rag-ai/settings/rules.
Edit the existing `aqlyra-main-production-gate` ruleset instead of creating a duplicate. Preserve the 11 required job checks and deletion/non-fast-forward restrictions. Set required approving reviews to **at least 1 independent reviewer**, dismiss stale approvals on new commits, and enable last-push approval where supported. Keep bypass permissions empty. The JSON template remains a reference; importing it as a second ruleset is not necessary.
Do not include an admin bypass; if GitHub rejects any imported field,
review it explicitly instead of silently downgrading enforcement.

- Ruleset name: `aqlyra-main-production-gate`
- Enforcement: **Active**, not Evaluate or Disabled.
- Target: **Default branch (`main`) only**. Do not protect the feature and
  integration branches by accident.
- Restrict deletions: on.
- Block force pushes: on.
- Require a pull request before merging: on.
- Required approving reviews: **at least one independent reviewer**.
  Prefer dismissing stale approvals on new commits.
- Require status checks to pass: on; require every job below.
- Expected check source: GitHub Actions, where selectable.
- Bypass permissions: **none**, unless a documented emergency-only access
  process is authorized independently.
- Review the impact of requiring branches to be up-to-date. GitHub may request
  a fresh CI run when `main` advances.

### All required check names (11)

These are GitHub **job contexts**, not merely workflow display names.
Each runs on every pull request targeting `main` in the release candidate,
to prevent permanently pending required checks on docs-only changes.

1. `Python 3.13 / PostgreSQL 16`
2. `Frontend lint, typecheck and build`
3. `Validate staging smoke contracts`
4. `Validate production Compose configuration`
5. `Build production Docker images`
6. `Native ARM64 builds + real local reverse-proxy smoke`
7. `npm security audit`
8. `Python security audit`
9. `Check Markdown links and code fences`
10. `Always-on Merge Gate`
11. `High-severity Python SAST`

GitHub must list the corresponding checks after they have run. Do **not**
select similarly named checks from untrusted external sources.

If there is no independent collaborator who can review the release PR,
add a trusted reviewer before trying to merge. Do not weaken the policy
just to obtain a green badge.

## Separate release-branch ruleset (required)

The existing main ruleset does **not** protect release branches. The release
gate therefore requires a second active ruleset that explicitly covers the
candidate. It currently checks the exact branch
`release/study-abroad-included-20261129`; a pattern rule covering
`refs/heads/release/**` is also accepted.

Create `aqlyra-release-branches-gate` with:

- Enforcement: **Active**.
- Target: `refs/heads/release/**` (or exact candidate branch).
- Require pull requests and at least **one independent approving review**.
- Dismiss stale approvals on new commits; enable last-push approval where
  available.
- Require deletion restriction and non-fast-forward protection.
- Bypass actors: **none**.
- Require all **13 release job contexts** below.

### Required release job contexts (13)

The release ruleset must require the 11 contexts already used by the main
ruleset plus two stronger release checks:

1. `Python 3.13 / PostgreSQL 16`
2. `Frontend lint, typecheck and build`
3. `Validate staging smoke contracts`
4. `Validate production Compose configuration`
5. `Build production Docker images`
6. `Native ARM64 builds + real local reverse-proxy smoke`
7. `npm security audit`
8. `Python security audit`
9. `Check Markdown links and code fences`
10. `Always-on Merge Gate`
11. `High-severity Python SAST`
12. `Python 3.13 / PostgreSQL 18`
13. `Frontend CSRF, XSS and proxy security regression`

The frontend, ARM64 predeploy, documentation and Always-on Merge Gate
workflows have been updated to run for `release/**` pushes and pull requests.
Backend, dependency-audit and static-security workflows already cover
`release/**`. The regression test
`scripts/ops/test_release_security_workflow_coverage.py` guards this
coverage. Do not add a context as required until that job has completed
successfully on the candidate branch.

## Verify enforcement without changing production

1. Reopen the ruleset; ensure it says **Active** and targets `main`, with
   the exact 11 required job checks, at least one required review, and both
   deletion and force-push restrictions.
2. Inspect the full-scope release candidate PR, including Study Abroad, and verify required checks are populated
   on its **exact current head SHA**, not on a previous commit.
3. In the intended release branch checkout, use:
   ```sh
   python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v
   python3 scripts/ops/release_gate.py --json
   ```
   By default the script checks the Study-Abroad-included candidate branch. If another
   branch becomes the final candidate, pass
   `--release-branch <exact-branch-name>`; never assume PR #33 is latest.
4. Expect `production_approved=false` even if the automated release gate
   passes. Real staging, incident response, backup restore and explicit
   merge/deployment approval remain separate.

A missing or inaccessible Ruleset API response must **fail closed**.
This repository's connected GitHub App cannot execute the GitHub Rulesets
admin write endpoint. The repository administrator must perform the owner
setup through GitHub Settings or another explicitly authorized admin client.

## Never do these to make checks green

- Never merge a draft release PR before owner approval and staging acceptance.
- Never disable required checks, grant broad admin bypasses, or change
  `main` directly to work around a failing check.
- Never delete or recreate production PostgreSQL volumes, uploads, or
  embeddings as part of branch protection.
- Never treat GitHub's simulated CI stack as a real, external-provider
  production acceptance environment.

See [final release acceptance](RELEASE_ACCEPTANCE.md) and
[staging validation](STAGING.md).
