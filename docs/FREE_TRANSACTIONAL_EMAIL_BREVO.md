# Aqlyra — Free transactional email without owning a domain

Status: **integration prepared, NOT enabled on production**. Production
continues using the existing provider until the owner verifies a sender
and sets its private API credentials. Never treat a provider HTTP 201 as
confirmed inbox delivery.

## Why this option

- Existing Resend free testing sender `onboarding@resend.dev` can deliver
  real mail only to the Resend account owner's address until a private
  sending domain is verified; this cannot serve arbitrary Aqlyra users.
- Brevo Free supports transactional email over HTTPS, including on Render
  hosts without outgoing SMTP. Current Free plan advertises **300 email
  sends per day**, subject to provider account approval and delivery rules.
- Brevo permits verifying ownership of an individual sender mailbox via
  a 6-digit email challenge, but unauthenticated Gmail-origin mail may
  appear from a Brevo-rewritten technical sender address and may land in
  spam. This is a temporary free launch path, **not a substitute for an
  authenticated custom domain**.

Official references:
- https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans
- https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email
- https://help.brevo.com/hc/en-us/articles/14925263522578-Comply-with-Gmail-Yahoo-and-Microsoft-s-requirements-for-email-senders
- https://developers.brevo.com/reference/send-transac-email

## Activation: owner actions in Brevo

1. Create a **Free** account at https://www.brevo.com/ with a mailbox
   you control. Confirm account and any transactional sending approval.
2. Settings → Senders, Domains, IPs → Senders → Add a sender.
   Name: `Aqlyra`; sender mailbox: `aqlyra.verify@gmail.com`
   **only if the owner controls it**. Confirm the verification code that
   Brevo sends to that mailbox. This sender must show verified.
3. In Brevo, create a transactional **API v3** key privately. Do not use
   Brevo SMTP credentials, and never paste this key into GitHub/chat.
4. Before production cutover, change existing Render backend environment
   (no changes to app users or DB):
   ```dotenv
   EMAIL_DELIVERY_PROVIDER=brevo
   BREVO_API_KEY=<set only in Render private secrets>
   SMTP_FROM_NAME=Aqlyra
   SMTP_FROM_EMAIL=aqlyra.verify@gmail.com
   ```
   Never set SMTP_FROM_EMAIL to `Aqlyra` or `Aqlyra <...>`—the
   value must be only a bare validated email address. Remove unused
   provider secrets when appropriate. Retain
   `EMAIL_VERIFICATION_REQUIRED=true`.
5. Deploy the **same verified exact GitHub Full Release commit** to the
   existing Render `aqlyra-api-free-launch` service after its separate
   backup, storage, security and provider release gates. The connected
   Render app cannot change the service's Git branch, so the account
   owner must select the intended approved branch under Render settings
   first; leave auto-deploy OFF until authorized.
6. From the real HTTPS app, test account registration, OTP receipt,
   one-time verification, verified-user password reset, expiry, abuse
   rate limits and cross-user isolation. Examine provider delivery events
   with no OTP or user content in logs. Test Gmail and a second unrelated
   mailbox provider. If any failure occurs, revert to the previously
   working provider without disabling verification.

## What users see as the sender

- Requested display name: **Aqlyra**.
- Requested sender mailbox: **aqlyra.verify@gmail.com** (after owner
  verifies it with Brevo).
- **Actual From address may be rewritten by Brevo**, e.g.
  `aqlyra.verify@<brevo-account-number>.t-sender-sib.com` for
  transactional email. The account number is assigned by Brevo and must
  not be invented. Inspect a real delivered message before publishing a
  concrete From address.
- When an authenticated domain is available, switch the configured
  sender to `verify@<owned-domain>` and verify its DNS in the provider.

## Engineering and security

The existing `send_verification_email` and `send_password_reset_email`
functions share `_send_message`. Setting the provider to `brevo`
uses POST `https://api.brevo.com/v3/smtp/email` with an HTTP API
key header and a prevalidated sender mailbox. The API key and OTP
never appear in error exceptions or user-facing errors. Unexpected
status, invalid configuration or transport errors fail closed; no code
is delivered or reused. SMTP and Resend remain separate supported
options and are not automatically migrated.

**Acceptance:** the owner must verify a real delivery (Brevo API
accepted + actual recipient inbox), not just green CI or HTTP 201.
