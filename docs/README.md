# Documentation

[Project overview](../README.md)

## Understand the project

| Guide | What it explains |
|---|---|
| [Architecture](ARCHITECTURE.md) | Components and service boundaries |
| [RAG pipeline](RAG_PIPELINE.md) | Retrieval, evidence, generation and validation |
| [Security and testing](SECURITY_TESTING.md) | Authentication, isolation and regression coverage |
| [Project status](PROJECT_STATUS.md) | Source versus deployed releases and evidence limits |

## Run and develop

| Guide | Use it for |
|---|---|
| [Local Docker setup on macOS](MAC_LOCAL_SOFTWARE.md) | Full stack with a local verification inbox |
| [Setup](SETUP.md) | Manual setup, provider settings and test commands |
| [Frontend](../frontend/README.md) | UI development and frontend checks |

## Evaluate

- [Retrieval baseline](../backend/evaluation/BASELINE.md): controlled synthetic experiments; deterministic embeddings are not semantic-quality evidence.
- [Performance baseline](PERFORMANCE_BASELINE.md): read the recorded environment and methodology before interpreting results.
- [Scripted portfolio demo](VERCEL_PORTFOLIO_DEMO.md): backend-free UI walkthrough and hosting instructions.

## Deploy and operate

- [Staging and release gate](STAGING.md)
- [Oracle deployment guide](ORACLE_ALWAYS_FREE.md)
- [Operational scripts](../scripts/ops)

Deployment guides describe specific configurations. They are not proof that the hosted application currently uses that configuration. Release branches and pull requests retain their own rollout history; see [project status](PROJECT_STATUS.md).
