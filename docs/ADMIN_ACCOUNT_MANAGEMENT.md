# Admin account management and verified mailbox handoff

## Existing production identities

The platform has an authenticated, verified-UUID admin allowlist
(\`ADMIN_USER_IDS\`). This extension also supports exactly one opt-in verified
mailbox through the **server-side** \`ADMIN_OWNER_EMAIL\` environment variable.
Both are disabled by default; no browser/public environment variable or
email-only unverified signup can grant authority.

The requested \`aqlyra.verify@gmail.com\` address must be registered (or linked
through the existing authorized Google login) **and email verified**. On the
Render service, set \`ADMIN_OWNER_EMAIL=aqlyra.verify@gmail.com\` privately.
The prior UUID admin remains valid until the mailbox holder has logged in and
confirmed \`/api/auth/me\` responds \`is_admin:true\` and \`/admin\` loads.
Only then consider revoking \`ADMIN_USER_IDS\` in a separate controlled change.
Never treat ownership of the mailbox as verified merely because its address
is written in configuration.

## Account management in existing /admin

\`GET /api/v1/admin/users?q=&limit=25&offset=0\` returns a bounded,
paged, server-authorized inventory of email, username, verification,
registration date, and active status. It never returns hashed passwords,
JWTs, message text, document content or session tokens.

\`PATCH /api/v1/admin/users/{id}/status\` requires verified admin login,
exact matching target email, and action disable/enable. It increments
\`auth_epoch\` to revoke older access/refresh tokens when status changes.
The current admin, other admins, and any identity reserved for the configured
owner email are protected from modification.

\`DELETE /api/v1/admin/users/{id}\` is **disabled by default** via
\`ADMIN_ACCOUNT_DELETION_ENABLED=false\`. When deliberately enabled after
storage and restore acceptance, it requires an already disabled target,
matching account email, exact literal \`DELETE ACCOUNT\`, and no recorded
documents or cloud-upload intents. This is a destructive DB cascade for
eligible accounts, not a complete erasure system for uploaded files and
backups. Accounts holding uploaded data get HTTP 409 and cannot be deleted
with this endpoint. Admins cannot delete themselves or other admins.

## Release gates

1. Backend PG16/PG18 full suite and security tests.
2. Frontend typecheck/build and API proxy CSRF/no-store tests.
3. Stage backend first, frontend next. Check anonymous 401, ordinary 403,
   verified admin 200 and account list confidentiality.
4. Grant owner-mailbox email only in private Render env; do not replace other
   variables. Keep current UUID admin active until new verified mailbox
   account can sign in and pass ownership validation.
5. Keep irreversible deletion feature disabled until separate verified
   restore/object cleanup and operator approval. No test/prod accounts
   should be deactivated or deleted by an automated deployment.
