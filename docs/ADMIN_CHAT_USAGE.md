# Aqlyra private Admin dashboard — usage metrics

The existing application already has a protected `/admin` page, backed by
`GET /api/v1/admin/overview`. This enhancement **extends** the current page
instead of introducing a second admin identity provider.

## Access control (fail closed)

1. Sign in with a verified Aqlyra account.
2. Obtain the account's **immutable UUID** from its authenticated `/users/me`
   response. Never put an access token, password, or cookie in a ticket.
3. On the **Render backend service only**, privately configure
   `ADMIN_USER_IDS=<exact-account-uuid>`. It is empty by default and permits
   no user. Do not use email addresses, usernames, Vercel public variables,
   or UI-only checks to grant access.
4. After the appropriate backend deployment and configuration, sign in and open
   `https://aqlyra-ai.vercel.app/admin`. Other accounts must receive HTTP 403
   at the backend (the frontend shows a 404). Admin JSON responses are no-store.

## What the new numbers mean

- **Registered / enabled / verified**: PostgreSQL account status.
- **Active chat users (24h / 7d)**: distinct authenticated account IDs with
  a *persisted user-role chat message* in the trailing 24 hours / 7 days.
- **Chat messages (24h / 7d)**: number of persisted user-role messages over
  those intervals. Assistant messages are excluded.
- **Daily activity**: UTC calendar dates for the current date and previous six.
- **API requests**: per backend process, resets on restart.

These are **not** live-online users, unique website visitors, unique devices,
guest traffic, or voice-session totals. They exclude users who only open
the site, users whose requests fail before persistence, and non-chat events.
All results are aggregates: no emails, user IDs, private chat content, IPs,
documents, or filenames are included in the new chat activity payload.

## Release safety

- No database migrations, data backfills, destructive queries, or secrets in Git.
- No changes to login, authorization, document isolation, chat/voice generation,
  or existing deployment settings.
- Run backend PostgreSQL test suite (including
  `backend/tests/test_admin_monitoring.py`) and frontend build/tests.
- Deploy the backend extension **first**; then deploy the matching frontend.
  A frontend deployed before the backend extension could see missing metrics.
- Check anonymous/normal-user 401/403, verified allowlisted admin 200,
  privacy-safe payload, no-store headers, uptime, and production error logs.
