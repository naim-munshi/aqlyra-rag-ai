# Security and Testing

## What is covered

Aqlyra includes application-level security controls for authentication, user isolation, uploads, RAG behavior, rate limiting, logging, and production configuration.

The test suite also checks a number of failure and adversarial cases.

## Authentication and ownership

Protected data is always read in the context of the authenticated user.

Ownership checks cover:

- documents;
- document content;
- conversations;
- messages;
- memory;
- Knowledge document scopes.

The backend does not treat a client-supplied user ID as proof of ownership.

## Cross-user access tests

The tests include cases where one user tries to access another user's:

- document;
- conversation;
- memory;
- document scope.

They also cover random IDs, missing authentication, and invalid scope combinations.

## Upload handling

Upload checks include:

- allowed extensions;
- size limits;
- filename sanitization;
- long filenames;
- corrupt inputs;
- parser failures.

The long-filename regression tests are important because filename sanitization must not remove a valid extension.

## RAG safety

Knowledge mode checks both citation syntax and evidence support.

The tests cover:

- malformed citations;
- unknown source IDs;
- missing citations;
- citation laundering;
- unsupported claims;
- failed grounding checks;
- repair/refusal behavior.

A correct-looking `[S1]` label is not accepted if `[S1]` does not support the claim.

## Rate limiting

Redis-backed rate limits protect expensive and authentication-sensitive endpoints.

That includes areas such as:

- registration;
- login;
- repeated failed login attempts;
- uploads;
- document processing;
- RAG answers;
- normal chat generation;
- voice sessions.

Rate-limit responses use `429` and include `Retry-After`.

If Redis is required for the operation and unavailable, the protected route fails closed.

## Production configuration checks

The production configuration rejects unsafe settings such as:

- debug mode;
- wildcard or localhost CORS;
- weak application secrets;
- weak/default database credentials;
- disabled rate limiting;
- deterministic production LLM configuration;
- disabled grounding verification.

Production API docs/OpenAPI are disabled.

## Logging

Production logs use structured JSON.

The logging path avoids intentionally recording request bodies or credentials.

Sensitive values such as tokens, secrets, and emails are redacted where they can appear in operational events.

Unhandled errors return a generic response instead of exposing internal details.

## Monitoring and alerting

Metrics use bounded labels instead of raw document or conversation IDs.

The alert worker is tested for:

- firing;
- duplicate suppression;
- recovery;
- resolved events;
- secret-free payloads.

## Test suite

The backend currently contains 70 `test_*.py` modules.

Coverage includes:

```text
authentication
tenant isolation
document ingestion
OCR
chunking
embeddings
dense retrieval
lexical retrieval
hybrid retrieval
RRF
retrieval evaluation
RAG context building
citation validation
semantic grounding adversarial cases
provider failures
conversation streaming
memory
voice sessions
production configuration
rate limiting
observability
monitoring
Redis readiness
alerting
```

## Test database

Backend tests use a separate PostgreSQL database:

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aqlyra_rag_ai_test
```

The test suite must not be pointed at the normal development database because some fixtures recreate database state.

## Failure cases covered

Examples include:

- cross-user IDOR attempts;
- malformed uploads;
- corrupt files;
- long filenames;
- citation laundering;
- grounding failures;
- provider 429s;
- provider timeouts;
- provider network errors;
- Redis outage;
- alert firing and recovery;
- backup verification.
