# Aqlyra Gmail API HTTPS — production OTP setup

**Status:** The `gmail_api` provider implementation is on the Full Release
branch but is **not enabled in Render**. Gmail API enabled in the owner's
Google Cloud project does not automatically authorize sending as a mailbox.

## Use case

The owner already enabled Gmail API. For a low-volume **private beta**
without a paid custom domain, send verification and password-reset email
using the owner-controlled mailbox `aqlyra.verify@gmail.com` via Gmail's
HTTPS API.

The recipient **will see the real sender email address** in the From field:
`Aqlyra <aqlyra.verify@gmail.com>`. A display name does **not** conceal
the actual mailbox address. A separate verified business domain/address is
needed if the owner wants a brand-specific sender. Gmail may apply its own
sending quotas, anti-abuse limits and verification requirements. This is
not an unlimited public transactional email service.

## Minimum owner authorization

1. In the existing Google Cloud project, verify that a confidential OAuth 2.0
   **Web application** or installed application client is configured for
   Gmail send authorization. The Gmail API being enabled alone is not enough.
2. Consent as the *owner of the sender mailbox* and request **only**
   `https://www.googleapis.com/auth/gmail.send`, with offline access.
   Capture an OAuth refresh token securely using Google's authorization
   code flow. Do **not** put OAuth secrets in chat, GitHub, application frontend
   code, URL query parameters, or NEXT_PUBLIC variables. The official
   Google OAuth Playground requires entering your client credentials
   into its protected configuration flow; use it only knowingly. The refresh token gives
   sending privileges and should be treated like a password.
3. In the existing Render **private environment** set:

   ```dotenv
   EMAIL_DELIVERY_PROVIDER=gmail_api
   SMTP_FROM_NAME=Aqlyra
   SMTP_FROM_EMAIL=aqlyra.verify@gmail.com
   GMAIL_OAUTH_CLIENT_ID=<private OAuth client ID>
   GMAIL_OAUTH_CLIENT_SECRET=<private OAuth client secret>
   GMAIL_OAUTH_REFRESH_TOKEN=<private authorized offline refresh token>
   ```

4. Leave `EMAIL_VERIFICATION_REQUIRED=true`, `RATE_LIMIT_ENABLED=true`
   and existing auth ownership checks unchanged. Do not enable an arbitrary
   public sender or store Gmail credentials in the repo.
5. Deploy the **same tested Full Release backend commit** on the existing
   Render service, after branch, database backup and provider gates.
6. Verify a real newly issued OTP reaches a Gmail inbox and another provider
   inbox; verify one-time redemption, expiry, failed delivery and
   password-reset after email verification. Gmail API HTTP 200 means the
   message was accepted by Gmail, not that the recipient inbox received it.

### Phone-friendly owner authorization using Google's OAuth 2.0 Playground

Only the **mailbox owner** can grant sending access. This operation is separate
from user-facing "Continue with Google"; customers never authorize Aqlyra to
send from their own Gmail accounts.

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   select the existing Aqlyra project and its Gmail-enabled API. Open
   **Google Auth Platform → Clients**. Create/select a **Web application**
   OAuth client for email sending (keep this separate from the public
   Google Sign-In client where possible). Add the exact authorized
   redirect URI `https://developers.google.com/oauthplayground`.
2. In **Google Auth Platform → Data Access**, request the **single**
   sensitive scope `https://www.googleapis.com/auth/gmail.send`.
   When OAuth audience is External/Testing, add the sender Gmail account
   to **Test users**. An External/Testing refresh token commonly expires
   after 7 days; this is **not** durable production readiness.
3. Open the official
   [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
   in a browser (phone browser with Desktop Site enabled is possible).
   Open the gear icon, select **Use your own OAuth credentials**, and enter
   your Web client's ID/secret **only into this official Google tool**.
   Confirm **Server-side**, **Offline** access and **Consent Screen**.
   Google notes that OAuth Playground proxies these credentials through
   its server; an owner-managed OAuth callback is preferable for long-term
   authorization.
4. Enter only `https://www.googleapis.com/auth/gmail.send` in Step 1,
   select **Authorize APIs**, and sign in **as the sender account**.
   In Step 2 select **Exchange authorization code for tokens** and retain
   the refresh token privately. Never send that token, the OAuth client
   secret or a screenshot of them to chat, GitHub, Vercel public variables,
   logs or an email.
5. In existing Render service → **Environment**, set the six provider
   settings shown below as private variables and keep
   `EMAIL_VERIFICATION_REQUIRED=true`. Do not configure this on Vercel:
   OTP sends originate from the FastAPI backend.
6. **After** the Full backend recovery/cutover gate, deploy the same
   reviewed Full commit and test an OTP from a new test signup. Check
   inbox and spam, one-time redemption, expiration and password reset.
   An HTTP 200 or Gmail message ID alone is **not** inbox-delivery proof.
7. For external production users, review
   [Google's Gmail-scope OAuth verification rules](https://developers.google.com/workspace/gmail/api/auth/scopes)
   and move beyond Testing only when the owner's consent-screen
   publishing/verification requirements are satisfied. Do not promise
   continuous sending on a seven-day test token.

### Important 7-day token limitation

Google OAuth apps with an **External** consent screen still in **Testing**
normally issue refresh tokens that expire after **7 days** for Gmail scopes.
A green one-off test is not stable production sending. Review the actual
OAuth app publishing status and relevant Google verification requirements
before enabling customer signups.

Sources:
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send
- https://developers.google.com/workspace/gmail/api/auth/web-server
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://support.google.com/cloud/answer/15549945

## Engineering

The new provider issues a `grant_type=refresh_token` HTTPS request
to `https://oauth2.googleapis.com/token` server-side, then posts a
base64url RFC822 `raw` message to
`https://gmail.googleapis.com/gmail/v1/users/me/messages/send`.
No SMTP egress or custom domain is needed. It refuses missing credentials,
invalid sender, invalid access token, non-200 response and missing
message ID; exceptions omit provider responses, OTPs and secrets.
Both registration and password reset reuse the existing single-use
code path. Gmail API quota and mailbox limits still apply.

Do **not** assume Google Sign-In client configuration authorizes sending mail.
This OAuth grant is separate and sends only from the account that approved
the Gmail scope.
