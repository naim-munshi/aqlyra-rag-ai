# Aqlyra Gmail API HTTPS — production OTP setup

**Status:** The `gmail_api` provider implementation is on the Full Release
branch but is **not enabled in Render**. Gmail API enabled in the owner's
Google Cloud project does not automatically authorize sending as a mailbox.

## Use case

The user already enabled Gmail API. For a low-volume initial beta without
a paid sending domain or displaying a physical mailing address, send
verification and password-reset email using the owner-controlled mailbox
`aqlyra.verify@gmail.com` via Gmail's HTTPS API.

Sender: `Aqlyra <aqlyra.verify@gmail.com>`. Gmail may apply its own
sending quotas and anti-abuse limits. This is not an unlimited public
transactional email service.

## Minimum owner authorization

1. In the existing Google Cloud project, verify that a confidential OAuth 2.0
   **Web application** or installed application client is configured for
   Gmail send authorization. The Gmail API being enabled alone is not enough.
2. Consent as the *owner of the sender mailbox* and request **only**
   `https://www.googleapis.com/auth/gmail.send`, with offline access.
   Capture an OAuth refresh token securely using Google's authorization
   code flow. Do **not** put OAuth secrets in chat, GitHub, the browser,
   URL query parameters, or NEXT_PUBLIC variables. The refresh token gives
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
