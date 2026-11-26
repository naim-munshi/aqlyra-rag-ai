# Knowledge Research Agent Harness

Status: feature branch implementation, disabled by default.

## Runtime boundary

The research agent is an opt-in mode inside Knowledge chat. It is a single bounded agent, not a multi-agent orchestrator. Its only tool is `knowledge.search_documents`, which calls the existing owner-scoped retrieval service with the authenticated user's ID and optional document allowlist.

The execution path is:

1. Validate question length and reject a small set of explicit prompt-override patterns.
2. Mask common email addresses and phone-number patterns before the request reaches retrieval, generation or persistent traces.
3. Build a deterministic plan of at most three short retrieval queries.
4. Retrieve owner-authorized chunks and keep only chunk IDs/counts in the trace.
5. Pass the exact collected hits to the existing RAG answer path for citation and grounding validation.
6. Return the answer only when the existing RAG validator accepts its citations; otherwise abstain.
7. Persist the run and step trace, and settle the reserved daily budget.

The agent does not accept arbitrary tool names, URLs, SQL, shell commands, browser actions or user-supplied model instructions. It cannot access other users' documents through the Knowledge retrieval tool.

## API

All routes are under `/api/v1/agent-harness` and require the normal Aqlyra access token.

- `POST /research`: run one bounded research request.
- `GET /runs?limit=20`: list the authenticated user's recent runs.
- `GET /runs/{run_id}`: fetch one of that user's traces.

The frontend uses cookie-authenticated Next.js route handlers as a private BFF. Mutating browser requests enforce same-origin provenance, bodies are bounded, responses use private no-store cache headers, and backend calls forward the existing bearer token.

The trace viewer is at `/agent-harness`. It shows recent runs, model, token counts, latency, estimated cost and a step timeline. The trace list and details are always filtered by `user_id`; a trace belonging to another account returns 404.

## Guardrails and trace privacy

- Input length: 1–2,000 characters.
- Retrieval calls: at most three.
- Total trace steps: at most seven by default (input guardrail, plan, retrieval calls, synthesis, output guardrail).
- Retrieved chunk content is not copied into trace rows; traces store chunk IDs, counts, tool names and redacted query summaries.
- Email and common phone patterns are masked. This is targeted masking, not a complete PII detector.
- The existing RAG citation validator remains authoritative; the agent does not replace it.
- No evidence or invalid citations result in a safe abstention.
- Failed runs are stored with an error class only; raw provider responses, secrets and exception text are not persisted.

Tables added by the feature migration:

- `agent_runs`: one owner-scoped record per run.
- `agent_steps`: ordered tool, guardrail, plan and synthesis steps.
- `agent_daily_usage`: daily per-user request, token and cost totals.

## Cost and daily budget

The agent fails closed unless both model rates are configured. The runtime reserves a maximum per-run estimate in Redis before any retrieval or generation. The reservation is atomic and keyed by a one-way hash of the user ID and UTC date. Redis unavailability blocks agent runs rather than bypassing the daily cap.

Completed token usage and cost are also written to PostgreSQL. If a provider does not report token usage, the trace uses the reserved upper bound instead of pretending the cost is zero.

Important accounting limitation: the current cost number covers measured language-model generation tokens only (or the conservative reservation when usage is unavailable). Embedding, query-rewrite, reranker and grounding-verifier provider costs are not itemized yet. The viewer labels the value as estimated and displays its cost basis; it must not be treated as a full invoice total.

### Required deployment settings

The feature stays off by default. Enable it only after applying the additive Alembic migration and confirming the active provider's published input/output price per one million tokens:

- `AGENT_HARNESS_ENABLED=true`
- `AGENT_INPUT_PRICE_PER_1M_USD=<current provider input price>`
- `AGENT_OUTPUT_PRICE_PER_1M_USD=<current provider output price>`
- `AGENT_DAILY_BUDGET_USD=0.25` (example daily ceiling)
- `AGENT_MAX_INPUT_TOKENS=12000`
- `AGENT_MAX_OUTPUT_TOKENS=2000`
- `AGENT_MAX_STEPS=7`
- `AGENT_MAX_RETRIEVALS=3`

Do not copy placeholder prices into production. Update the two price values whenever the configured LLM model changes. The feature is disabled if either value is missing, and Redis must be reachable. The migration is additive; it is not run automatically by this feature branch.

## Evaluation and CI gate

The golden fixture is `backend/evaluation/agent_harness_golden.json`. CI runs the guardrail and golden tests as a dedicated step before the full backend test suite. The API regression tests additionally exercise a deterministic grounded answer, citation presence, step limits, owner-only trace access and fail-closed disabled mode. Frontend static contract tests check the opt-in Knowledge toggle, BFF origin/session checks and trace viewer boundary.

These first CI metrics are deterministic regression gates (citation presence, abstention, guardrail rejection, step completeness and tenant isolation). RAGAS LLM-judge metrics such as faithfulness, answer relevancy and context precision/recall are not enabled in CI yet: they need a separately budgeted judge provider and calibrated reference contexts. They must not silently introduce paid model calls into every pull request.

## Not included

Multi-agent orchestration, autonomous browser/web tools, arbitrary function calling, automatic prompt optimisation, fine-tuning, user-facing approval workflows and production enablement are outside this first branch.
