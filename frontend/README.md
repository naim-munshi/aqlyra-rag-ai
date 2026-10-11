# Aqlyra Frontend

Next.js 16, React 19, and TypeScript web application for the Aqlyra AI knowledge platform. The frontend provides verified authentication, Converse and Knowledge workspaces, conversations, document workflows, and optional voice sessions.

The browser uses same-origin Next.js API routes. Server-side route handlers forward authenticated requests to FastAPI using the HttpOnly session cookie. The backend access token is not exposed to browser JavaScript.

## Requirements

- Node.js 24 and npm
- A running Aqlyra backend with PostgreSQL (and Redis when rate limiting is enabled)
- SMTP credentials for email-code verification, or a configured Google Web Client ID for Google sign-in

## Local development

Start the backend services from the repository root using the [setup guide](../docs/SETUP.md), then run:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Configure `frontend/.env.local`:

```dotenv
BACKEND_API_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=
```

To use Google sign-in, set the public Client ID to the same value as `GOOGLE_CLIENT_ID` in `backend/.env`. It is not an OAuth client secret.

Open [http://localhost:3000](http://localhost:3000). Unauthenticated users are redirected to `/login`. The development backend uses deterministic LLM/embedding defaults unless real model providers are configured.

## Quality and security checks

From `frontend/`:

```bash
npm run lint
npx tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
npm run build
```

The tests check same-origin state-changing API request protection in `src/proxy.ts` and `src/lib/security/origin.ts`. The production app uses HttpOnly, Secure and SameSite session cookies; FastAPI independently enforces ownership and JWT validation.

## Deployment

The supported full-stack deployment uses Docker Compose and Caddy with HTTPS termination. The Next.js runtime container uses an unprivileged user. The public `NEXT_PUBLIC_GOOGLE_CLIENT_ID` must be supplied at **image build time**, while `BACKEND_API_URL` points to the internal FastAPI address.

The frontend image alone does not include PostgreSQL, Redis, the voice worker, SMTP delivery or hosted AI model services. For actual rollout procedures, see [Staging and Release Gate](../docs/STAGING.md) and [Setup](../docs/SETUP.md). Do not deploy with example secrets.

## Documentation

- [Project overview](../README.md)
- [Architecture](../docs/ARCHITECTURE.md)
- [Security and Testing](../docs/SECURITY_TESTING.md)
- [RAG Pipeline](../docs/RAG_PIPELINE.md)
