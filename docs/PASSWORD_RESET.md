# Aqlyra password recovery

Account recovery is distinct from registration email verification. The login
screen's **Forgot password?** link opens `/forgot-password`.

1. POST `/api/v1/auth/request-password-reset` with `{"email":"..."}`.
   The reply is always generic, including unknown/ineligible accounts and
   cooling-down accounts. Verified active accounts receive a six-digit code.
2. POST `/api/v1/auth/reset-password` with `email`, `code`, and
   `new_password`. Code expires in 10 minutes; five wrong guesses consume
   the challenge. Only the HMAC digest is stored, and it is purpose-separated
   from the registration OTP. Reissued codes supersede older codes.
3. Successful recovery replaces the password and increments `users.auth_epoch`;
   previously issued access JWTs fail authentication. Google sign-in remains
   linked to the verified Google identity.

Operational notes:
- New Alembic migration: `f18a3c42e917`. Apply to the **intended** database
  after taking a verified backup: `cd backend && .venv/bin/alembic upgrade head`.
- Frontend communicates with FastAPI via `BACKEND_API_URL` as before.
- The existing SMTP settings are reused. The UI never returns a reset code.
- Redis IP rate limiting is enforced when `RATE_LIMIT_ENABLED=true`.
  Independently, a 60-second per-account resend cooldown and five-attempt
  invalid-code limit are always enforced by PostgreSQL.
- Validate locally with a real SMTP sink/account and backend tests before
  releasing publicly. Never include one-time codes in issue screenshots or logs.
- On Google-only accounts, a verified email owner can choose a local password.
