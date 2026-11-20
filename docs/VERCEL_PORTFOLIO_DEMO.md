# Archived: Aqlyra public portfolio preview (disabled)

The scripted public portfolio preview has been retired from the active Aqlyra
application. The production frontend no longer exposes the preview:

- `/demo` redirects to `/login`.
- Login, public home and About pages do not link to the preview.
- The sitemap no longer publishes `/demo`.
- Legacy `NEXT_PUBLIC_AQLYRA_DEMO_ONLY` values do not redirect anonymous
  visitors to the preview.

This change affects only the former public sample walkthrough. The actual
authenticated Next.js application, login and registration flows, FastAPI
backend, database, user files, and workspace routes are unchanged.

The old scripted sample source is retained in the repository for historical
reference and tests, but the active route does not import or render it.
Do not use the historical Vercel preview instructions; there is no public
scripted-demo deployment in the current product.

For the current frontend and verification steps, see
[frontend/README.md](../frontend/README.md).
