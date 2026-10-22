# Aqlyra public portfolio preview (Vercel Hobby)

Aqlyra is a full-stack application, not a Vercel-only backend.
The public /demo route is an **intentional, transparent, browser-only**
walkthrough for recruiters, reviewers, and mobile visitors. It does not
contact FastAPI, PostgreSQL, Redis, an LLM provider, or a voice service.

The preview is separate from the actual authenticated app. Anonymous
visits to / redirect to /demo, while authenticated users still enter
the real workspace. /login and private APIs retain their original
behavior when a backend is available.

## What a visitor can do without an account

- Switch between the Knowledge and Converse sample workspaces.
- Select authored example questions to inspect illustrative answers.
- Inspect an example citation and corresponding *synthetic* policy excerpt.
- Explore the real system components and GitHub implementation.
- Use the same interface on mobile and desktop.

The simulated example content is identified in the UI. It does not
claim that an LLM or embedding model generated it, that a file was
uploaded, or that a private index was searched. Arbitrary prompts do
**not** yield fabricated responses.

## Recommended zero-cost portfolio setup

Use the **Vercel Hobby** plan for the Next.js frontend preview. It is
intended for personal, non-commercial usage; check current plan terms
and usage limits before connecting a repository.

1. Connect this GitHub repository to your personal Vercel account.
2. Create a new Vercel project. Set **Root Directory** to frontend.
3. Framework preset: **Next.js**. Install command: npm ci.
   Build command: npm run build. Do not change the application's
   current TypeScript, routing, or production Docker configuration.
4. Do not supply backend SECRET_KEY, database credentials, SMTP
   passwords or private API tokens in Vercel's public environment
   variables. The public demo does not need credentials or backend URLs.
5. Deploy on the **Hobby** plan; verify that https://YOUR_SITE/demo
   renders without a login or backend account.
6. Verify that the root URL redirects to /demo when unauthenticated
   and that all sample-mode buttons, prompts, mobile layout and citation
   disclosure work.
7. Verify that /login is a *separate real-app route*, **not** a
   functioning authentication promise for a frontend-only deployment.
   If the backend is unavailable, sign-in APIs will not work.

Do not create a new Supabase project just to power this preview. The
public demo needs no database, Redis instance, object storage,
background worker, VM or ongoing model inference.

## Check locally or in CI

From the repository root:

~~~bash
cd frontend
npm ci
npm run lint
npx tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
npm run build
~~~

This confirms route compilation, type safety and sample-data integrity.
Screenshots and interaction testing on actual Vercel HTTPS, Safari and
mobile browsers must still be verified after deployment.

## When the full app is available

The real application remains:

~~~text
Caddy -> Next.js -> FastAPI -> PostgreSQL/pgvector + Redis
                             -> LLM and embedding APIs
                             -> optional voice and alert workers
~~~

Deploy the complete stack using [Oracle Always Free](ORACLE_ALWAYS_FREE.md)
or an alternative host capable of persistent volumes and workers,
with documented staging tests and verified backups.

A Vercel Hobby frontend by itself is **not** a replacement for a
persistent FastAPI instance, background jobs, vector database,
rate limiting, uploads, production SMTP or voice infrastructure.

Existing deployments, SakuraGlam services and Supabase projects must
not be repurposed, overwritten or upgraded to paid services to launch
the Aqlyra portfolio preview.
