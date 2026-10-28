# Aqlyra — Google sign-in production activation

## Current verified status (2026-10-29)

- Sign in with Google frontend button and the server-side `/auth/google` route exist.
- The Google Identity Services credential is verified against the **exact**
  backend `GOOGLE_CLIENT_ID` audience, issuer, subject and verified email.
- Vercel project `aqlyra` currently has **no**
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` environment variable. The frontend now
  renders an explicitly **disabled** and labelled Google option rather than
  silently hiding it. This is not functional Google SSO.
- Production Vercel Authentication is enabled across all deployments.
  Do not remove that protection until the owner completes auth and private
  document durability acceptance.

## Required owner actions in Google Cloud

1. Open the Google Cloud Console → **Google Auth Platform** → **Clients**.
   Select an existing **Web application** OAuth client or create one.
2. Under **Authorized JavaScript origins** add the exact production origin
   `https://aqlyra-navy.vercel.app`. If the secondary canonical host is used
   by users, also authorize `https://aqlyra-aqlyra.vercel.app`.
   The values are origins, not `/login` URLs, and must use HTTPS.
3. Configure Google OAuth branding and audience (publishing status/test users).
   For public sign-in, ensure the app is permitted for the intended audience.
4. Copy the **public Web Client ID** (ends in `.apps.googleusercontent.com`).
   This particular ID is not a secret. Never paste a Google client secret.
5. Add that exact Web Client ID **only** to:
   - Vercel `aqlyra`, production: `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
   - Render `aqlyra-api-free-launch`: `GOOGLE_CLIENT_ID`
6. Keep existing `BACKEND_API_URL`, JWT signing secret, Redis throttling,
   and email-verification policy. **Do not disable email validation, set an
   invented OAuth ID, or accept arbitrary token audiences.**
7. Redeploy the Vercel production frontend after adding `NEXT_PUBLIC_...`:
   Next.js bundles this value into the browser at **build time**. A backend
   restart/redeploy may be required when Render settings change.
8. On a real iPhone, open the canonical origin in **Safari**, not an embedded
   browser/webview. Google Identity Services does not support all webviews.

## Required acceptance (NOT YET PASS)

- Google button is visible and interactive on production `/login` and
  `/register` when the public Client ID is configured.
- Google account chooser returns a credential to the frontend; server
  verifies the expected Google JWT audience, issuer and verified email.
- Valid login creates an HttpOnly session and redirects to the signed-in
  dashboard; invalid, expired or wrong-audience credentials are rejected.
- No pre-existing email/password account is silently linked to a different
  Google subject.
- Google origin is allowed in Cloud Console and both frontend/backend use
  the **same** Client ID. No client secret is needed in the current ID-token
  verification flow.
- Two separate Google identities cannot see one another's documents,
  conversations, Study Abroad cases or admin data.
- Log out revokes the session and clears the browser cookie.

Google identity activation alone does **not** authorize opening the site
to unprotected public registrations. Full database backup/recovery and
real durable private S3 plus two-user E2E are separate release gates.

Official setup:
https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
