# GitHub main branch ruleset - owner setup and verification

Status as checked on 2026-10-27: `main` is not protected and there are no
active repository rulesets. **This requires a GitHub repository administrator's
explicit action.** GitHub's connected code integration cannot update Rulesets;
do not confuse an always-on CI job with enforced branch protection.

## Owner action - create one enforced ruleset

Open https://github.com/naim-munshi/aqlyra-rag-ai/settings/rules.
**Fastest:** choose **New ruleset > Import a ruleset** and select
[the ready-to-import Aqlyra ruleset JSON](aqlyra-main.ruleset.json).
Review all settings and select **Create**. This imports the 11 job checks,
requires an independent PR review, and enables force-push/deletion protection.
If import is unavailable, use **New branch ruleset** and the fields below.
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

## Verify enforcement without changing production

1. Reopen the ruleset; ensure it says **Active** and targets `main`, with
   the exact 11 required job checks, at least one required review, and both
   deletion and force-push restrictions.
2. Inspect the latest core release PR, excluding Study Abroad, and verify required checks are populated
   on its **exact current head SHA**, not on a previous commit.
3. In the intended release branch checkout, use:
   ```sh
   python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v
   python3 scripts/ops/release_gate.py --json
   ```
   By default the script checks the core release branch. If another
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
