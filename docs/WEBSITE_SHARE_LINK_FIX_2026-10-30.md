# Aqlyra — shared website link acceptance (2026-10-30)

## Canonical address and observed behavior

- Verified public-facing project aliases: `https://aqlyra-ai.vercel.app` (preferred) and `https://aqlyra-navy.vercel.app` (legacy). These aliases currently resolve to the same protected frontend deployment.
- `https://aqlyra.vercel.app` is **not assigned** to this Aqlyra Vercel project. Do not promote or print it as the production URL.
- Vercel project protection currently applies **to all deployments**, including the production alias. Copying the bare `aqlyra-ai.vercel.app` URL to an external user therefore leads to Vercel Authentication / access-request rather than the product login screen. This is not an API, DNS, OAuth, or mobile rendering failure.
- A Vercel **shareable testing link** has been regenerated with an owner-chosen 30-day TTL. Sharing that entire URL, including its Vercel access query parameter, allows test visitors to see the protected production frontend without changing the project's global protection setting. The access URL is an access credential: **do not** store it or its query token in source code, CI logs, analytics, public docs, or screenshots. Revoke it if it leaks or abuse is detected.
- Authenticated read-only Vercel web checks: `/`, `/login`, `/register`, and `/api/health` returned HTTP 200; `/signup` returned 404 on the previous deployment. The Full Release source now redirects `/signup` → `/register` and `/signin` → `/login`. These fixes are **not live until a reviewed frontend deployment**.

## Test/share instructions

1. The owner copies the current valid protected **shareable link** from Vercel → project → Deployments → Share. Share the entire URL, not its base hostname or a screenshot.
2. Ask the test visitor to open that URL first in a fresh normal browser tab (not from a stripped/truncated social preview). It establishes a Vercel view cookie and redirects to the application. On subsequent visits use the same browser and hostname.
3. They should reach the Aqlyra application sign-in, not a Vercel login. Product-specific signup, OTP, Google authorization and private files still use Aqlyra's own security checks; a Vercel bypass must not grant an Aqlyra account session.
4. If a visitor lands on the Vercel login screen, verify the full share URL was sent, its TTL has not expired, and the visitor's browser retained cookies. If the app's own login fails, investigate app authentication separately.
5. Never tell external visitors to enter password, OTP or payment data into a Vercel login they did not expect. Never send any actual production credentials with an access link.

## Permanent public release — separate security approval

To make the **bare** `https://aqlyra-ai.vercel.app` URL accessible to anyone permanently, the owner must explicitly approve a change to the Vercel production protection scope. Prefer preserving protection on previews and internal deploy URLs rather than globally disabling Vercel Authentication.

Do **not** change this protection setting until private file durability, real account verification, Google OAuth/password-reset browser tests, real embedding provider availability, tenant security, backups/recovery and production release-owner acceptance have been completed. Sharing an access URL is not equivalent to passing those gates.

This runbook avoids committing bypass credentials or changing `main`, app database, Render backend, guest-access controls and any existing production alias.
