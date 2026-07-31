```markdown
# Ihsan RAG AI

**Ihsan RAG AI** is a production-oriented Retrieval-Augmented Generation (RAG) platform built with a modular architecture. The project is designed to deliver an enterprise-grade AI assistant capable of understanding private knowledge bases through document processing, intelligent retrieval, and conversational AI.

## What I Built

- Set up FastAPI backend with modular architecture (API, auth, services, models)
- Configured PostgreSQL database with Alembic migrations
- Implemented JWT-based authentication system
- Created Docker setup for easy deployment
- Designed project structure for scalability

## Features

- Document upload and processing (PDF, DOCX, TXT)
- Text chunking and embedding generation
- Vector storage using PostgreSQL and pgvector
- Hybrid retrieval combining semantic and keyword search
- JWT-based authentication
- Multi-LLM support (OpenAI, Claude, local models)
- Conversation memory for multi-turn interactions
- Docker-based deployment

## Tech Stack

- Backend: FastAPI, Python 3.10+
- AI/ML: LangChain, LangGraph
- Database: PostgreSQL 15+, pgvector, SQLAlchemy, Alembic
- Cache: Redis
- Infrastructure: Docker, Docker Compose

## Project Structure

```
ihsan-raq-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── config/
│   │   ├── core/
│   │   ├── database/
│   │   ├── middleware/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── uploads/
│   ├── logs/
│   ├── .env
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
├── docker/
├── docs/
├── scripts/
├── docker-compose.yml
└── .gitignore
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- PostgreSQL 15+ with pgvector

### Local Development

```bash
git clone https://github.com/naim-munshi/ihsan-raq-ai.git
cd ihsan-raq-ai/backend

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

alembic upgrade head
uvicorn app.main:app --reload
```

### Docker

```bash
docker-compose up --build
```

API available at http://localhost:8000

## API Endpoints

- POST `/api/v1/auth/register` - Register new user
- POST `/api/v1/auth/login` - Login and get JWT token
- POST `/api/v1/documents` - Upload document
- GET `/api/v1/documents` - List documents
- DELETE `/api/v1/documents/{id}` - Delete document
- POST `/api/v1/query` - Query knowledge base
- GET `/api/v1/health` - Health check

Full API documentation at `/docs`

## Current Status

- Backend foundation: Complete
- PostgreSQL and Alembic: Complete
- JWT Authentication: Complete
- Document processing: In progress
- RAG pipeline: Planned
- Frontend: Planned

## License

MIT License
```
