# Aqlyra RAG AI

Aqlyra is an AI knowledge system for working with private documents and general conversations.

It has two main modes:

- **Converse** is the general chat experience. It supports streaming replies, conversation history, memory, file attachments, image understanding, and voice integration.
- **Knowledge** is the document-grounded mode. It searches the user's selected documents, retrieves relevant evidence, generates an answer with citations, checks whether the citations are valid, and refuses when the evidence is not strong enough.

The project keeps the main AI stages separate so they can be tested and debugged independently: ingestion, retrieval, evidence selection, generation, citation validation, grounding, persistence, and operations.

## Identity and sessions

Aqlyra supports two verified sign-in paths:

- Email/password registration sends a six-digit verification code before the account can receive an authenticated session. Codes expire after 10 minutes, allow at most five failed attempts, and cannot be resent more often than once per minute by default.
- Google sign-in accepts a Google Identity Services credential only after the backend validates its audience, issuer, stable subject, email address, and Google's `email_verified` claim.

Email verification codes are generated with a cryptographically secure random source. The database stores an HMAC digest rather than the plaintext code, and issuing a new code consumes any older active code for the same user.

After either path succeeds, the backend issues the same application access token. The Next.js server stores that token in an HttpOnly, SameSite cookie and uses it for authenticated backend requests.

## Core capabilities

- Next.js 16, React 19, and TypeScript frontend
- FastAPI backend
- Verified email/password authentication with expiring six-digit codes
- Google sign-in with backend ID-token verification
- JWT-backed sessions stored in HttpOnly browser cookies
- User-scoped documents, conversations, and memory
- PDF, DOCX, PPTX, XLSX, TXT, Markdown, and CSV ingestion
- OCR for PNG, JPG, JPEG, and WEBP images
- IBM Granite multilingual embeddings
- PostgreSQL with pgvector
- PostgreSQL full-text search
- Hybrid dense + lexical retrieval
- Reciprocal Rank Fusion (RRF)
- `[S1]`-style source citations
- Citation validation
- Semantic grounding checks
- Answer repair and safe refusal
- Streaming chat
- Conversation history
- Mode-specific projects with automatic first-chat creation and first-turn titles
- Personal memory
- Turn-scoped attachments
- Multimodal image understanding
- Voice integration
- Redis-backed rate limiting
- Structured JSON logs
- Request IDs
- Prometheus-compatible metrics
- Health and readiness checks
- Internal alerting
- Backup and restore tooling
- Docker Compose deployment profile
- Caddy reverse proxy configuration

## How the system is structured

```mermaid
flowchart LR
    U[User] --> C[Caddy]
    C --> F[Next.js]
    F --> B[FastAPI]

    B --> PG[(PostgreSQL + pgvector)]
    B --> R[(Redis)]
    B --> L[LLM Provider]
    B --> E[Embedding Provider]

    D[Documents / Images] --> P[Parsing + OCR]
    P --> CH[Chunking]
    CH --> E
    E --> PG

    Q[Knowledge Query] --> DR[Dense Retrieval]
    Q --> LR[Lexical Retrieval]
    DR --> RF[RRF]
    LR --> RF
    RF --> CTX[Evidence Context]
    CTX --> L
    L --> CV[Citation Validation]
    CV --> GV[Grounding Check]
    GV --> A[Answer]
```

## Converse

Converse is the general chat path.

It uses conversation history, saved memory, and any files attached to the current turn to build context for the model.

It also supports image input and the voice worker.

Converse is intentionally more flexible than Knowledge mode because it is not limited to document evidence.

## Knowledge

Knowledge is the strict RAG path.

A Knowledge request goes through these steps:

1. Check which documents the user is allowed to search.
2. Run dense semantic retrieval.
3. Run lexical full-text retrieval.
4. Merge both rankings with RRF.
5. Remove duplicates and build a bounded evidence set.
6. Send the evidence to the LLM.
7. Validate the returned citations.
8. Check whether the cited evidence actually supports the claims.
9. Repair the answer when possible.
10. Refuse the answer when the evidence is not sufficient.

The point of keeping these stages separate is simple: if an answer is wrong, it is possible to tell whether the problem came from retrieval, evidence selection, generation, citation handling, or grounding.

## Retrieval and grounding

The current embedding model is:

```text
ibm-granite/granite-embedding-97m-multilingual-r2
```

Embedding dimension:

```text
384
```

The current configuration keeps query rewriting and the general LLM reranker disabled:

```text
RAG_QUERY_REWRITE_ENABLED=false
RAG_RERANKER_ENABLED=false
```

Both pieces still exist in the architecture, but they are not part of the default path.

## Security and isolation

Aqlyra checks ownership before returning user data.

That applies to:

- documents;
- document content;
- conversations;
- messages;
- memory;
- projects;
- Knowledge document scopes.

Other controls include:

- verified email/password and Google identity paths;
- expiring, attempt-limited email codes stored only as HMAC digests;
- HttpOnly, SameSite session and verification cookies;
- JWT token-type separation for access and verification tickets;
- upload validation;
- filename sanitization;
- production CORS validation;
- production secret validation;
- Redis-backed rate limiting;
- fail-closed behavior when the required rate-limit backend is unavailable;
- log redaction;
- generic responses for unhandled errors;
- disabled OpenAPI/docs in production;
- localhost-only backend and database bindings in the intended deployment layout.

See [Security and Testing](docs/SECURITY_TESTING.md).

## Observability

Operational endpoints:

```text
GET /api/v1/health
GET /api/v1/readiness
GET /api/v1/metrics
```

The backend records structured JSON logs with request IDs and timing data.

The metrics endpoint exposes request counts, status codes, latency histograms, unhandled exception counts, rate-limit rejections, and rate-limit backend failures.

The alert worker checks readiness and metrics and can report firing and resolved states for service failures, 5xx spikes, latency spikes, unhandled exceptions, Redis failures, and unusual rate-limit activity.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript |
| Backend | FastAPI, Python |
| Validation | Pydantic |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Vector search | pgvector |
| Lexical retrieval | PostgreSQL full-text search |
| Rank fusion | Reciprocal Rank Fusion |
| Migrations | Alembic |
| Rate limiting | Redis |
| Embeddings | IBM Granite multilingual via Hugging Face |
| LLM adapters | Groq / OpenAI-compatible providers |
| OCR | Tesseract / pytesseract |
| Voice | LiveKit architecture |
| Reverse proxy | Caddy |
| Containers | Docker Compose |
| Tests | pytest, FastAPI TestClient |
| CI | GitHub Actions |

## Repository structure

```text
aqlyra-rag-ai/
├── backend/
│   ├── alembic/
│   │   └── versions/              # database migrations
│   ├── app/
│   │   ├── alerting/              # alert checks and webhook delivery
│   │   ├── api/                   # FastAPI routes
│   │   ├── auth/                  # authentication and JWT handling
│   │   ├── chunking/              # document chunking
│   │   ├── config/                # application settings
│   │   ├── core/                  # logging, monitoring, rate limiting
│   │   ├── database/              # database engine and sessions
│   │   ├── embeddings/            # embedding providers
│   │   ├── llms/                  # LLM provider adapters
│   │   ├── middleware/            # request middleware
│   │   ├── models/                # ORM models
│   │   ├── parsers/               # document parsing
│   │   ├── product_identity/      # product identity settings
│   │   ├── prompts/               # prompt definitions
│   │   ├── query_rewriting/       # optional query rewrite layer
│   │   ├── rag/                   # context, citations, grounding
│   │   ├── reranking/             # optional reranking layer
│   │   ├── retrieval/             # retrieval and rank fusion
│   │   ├── schemas/               # request/response models
│   │   ├── services/              # application services
│   │   ├── voice/                 # voice worker
│   │   ├── websocket/             # realtime support
│   │   └── main.py                # FastAPI entry point
│   ├── tests/
│   ├── Dockerfile
│   ├── Dockerfile.voice
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── api/
│   │       ├── login/
│   │       ├── register/
│   │       ├── verify-email/
│   │       └── page.tsx
│   ├── Dockerfile
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RAG_PIPELINE.md
│   ├── SECURITY_TESTING.md
│   ├── SETUP.md
│   └── DEMO.md
├── scripts/
│   └── ops/
├── Caddyfile
├── docker-compose.yml
├── LICENSE
└── README.md
```

## Testing

The backend currently has 71 `test_*.py` modules.

The tests cover:

- password authentication and unverified-login rejection;
- email verification expiry, attempts, resend controls, and delivery failures;
- Google credential validation and account linking;
- cross-user isolation;
- document ingestion;
- OCR;
- chunking;
- embeddings;
- dense retrieval;
- lexical retrieval;
- hybrid retrieval;
- RRF;
- retrieval evaluation;
- RAG context building;
- citation validation;
- semantic grounding edge cases;
- provider failures;
- streaming conversations;
- memory;
- project CRUD, ownership isolation, and conversation assignment;
- voice session APIs;
- production configuration;
- rate limiting;
- observability;
- monitoring;
- Redis readiness;
- alerting.

Tests use a separate PostgreSQL test database instead of the normal development database.

## Local development

Start the backend services:

```bash
docker compose up -d --build
docker compose ps
```

Check the backend:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/readiness
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Verified login requires SMTP settings in `backend/.env` and the same
Google Web Client ID in backend and frontend configuration. Local secret
files are ignored by Git; see the setup guide for the required values.

Run backend tests from `backend/`:

```bash
TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aqlyra_rag_ai_test' python -m pytest -q
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

For the full setup, see [docs/SETUP.md](docs/SETUP.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [RAG Pipeline](docs/RAG_PIPELINE.md)
- [Security and Testing](docs/SECURITY_TESTING.md)
- [Setup](docs/SETUP.md)
- [Demo](docs/DEMO.md)

## License

See [LICENSE](LICENSE).
