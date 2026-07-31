# Ihsan RAG AI

Ihsan RAG AI is a modular Retrieval-Augmented Generation (RAG) platform under active development.  
The project is designed to evolve into an enterprise-grade AI assistant capable of working with private documents and knowledge bases through document processing, semantic retrieval, LLM-powered response generation, source citation, conversational memory, and voice interaction.

Project status: Active development  
Current phase: Backend and authentication foundation

## Current Implementation

### Backend Foundation

- FastAPI application
- Modular backend structure
- Versioned API routes under `/api/v1`
- Environment-based configuration
- Pydantic settings management
- CORS middleware
- Centralized application logging
- Swagger/OpenAPI documentation
- Root and health-check endpoints

### Database Foundation

- PostgreSQL running through Docker Compose
- pgvector-enabled PostgreSQL database
- SQLAlchemy ORM integration
- Database engine and session management
- Alembic migration system
- Initial database migration
- User database model
- UUID-based user identifiers
- Unique email and username constraints
- Created and updated timestamps

### Authentication Foundation

- Password hashing with bcrypt
- Password verification
- JWT access-token generation
- User registration schema
- User login schema
- User response schema
- User creation service
- User lookup by email
- User authentication service

### Current Development Focus

The authentication foundation is implemented, and the public authentication endpoints are being completed:

- User registration endpoint
- User login endpoint
- JWT token validation
- Current-user dependency
- Protected `/users/me` endpoint
- Authentication API tests

## Planned RAG Architecture

User  
  │  
  ▼  
Frontend application  
  │  
  ▼  
FastAPI backend  
  │  
  ├── Authentication  
  ├── Document management  
  ├── RAG pipeline  
  ├── Conversation memory  
  └── LLM router  
          │  
          ▼  
      LLM providers

## Planned RAG Pipeline

1. Document upload  
2. Document parsing  
3. Text cleaning  
4. Document chunking  
5. Embedding generation  
6. Vector storage  
7. Semantic or hybrid retrieval  
8. Context building  
9. LLM response generation  
10. Source citations  

The RAG pipeline above represents the intended architecture and is not yet implemented.

## Technology Stack

### Currently used

- Backend: FastAPI, Python
- Validation: Pydantic
- Database: PostgreSQL
- Vector support: pgvector
- ORM: SQLAlchemy
- Migrations: Alembic
- Authentication: JWT, bcrypt
- Infrastructure: Docker, Docker Compose
- API documentation: Swagger/OpenAPI

### Planned

- Frontend: Next.js, TypeScript
- Cache and working memory: Redis
- RAG orchestration: Custom services or LangGraph
- Embeddings: Configurable embedding providers
- Retrieval: Vector search, hybrid search, reranking
- AI models: Multiple LLM providers
- Voice: Speech-to-text and text-to-speech
- Quality: Automated tests and RAG evaluation
- Deployment: Containerized production deployment

## Project Structure

```text
ihsan-raq-ai/
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── config/
│   │   ├── database/
│   │   ├── middleware/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
├── docs/
├── scripts/
├── docker-compose.yml
├── README.md
├── LICENSE
└── .gitignore
```

This is a compact representation of the current repository. The internal structure will be documented further as additional modules are implemented.

## Local Development

### Prerequisites

- Python 3
- Docker Desktop
- Git

### Steps

1. Clone the repository

```bash
git clone https://github.com/naim-munshi/ihsan-raq-ai.git
cd ihsan-raq-ai
```

2. Start PostgreSQL

```bash
docker compose up -d
docker compose ps
```

3. Open the backend directory

```bash
cd backend
```

4. Create a virtual environment

```bash
python3 -m venv .venv
```

5. Activate the virtual environment

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

6. Install dependencies

```bash
pip install -r requirements.txt
```

7. Configure environment variables

Create a backend `.env` file with the required database and application settings.  
The `.env` file must remain private and must not be committed to GitHub.

8. Apply database migrations

```bash
alembic upgrade head
alembic current
```

9. Start the backend

```bash
python -m uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

## Available Endpoints

- `GET /` — Root endpoint  
- `GET /api/v1/health` — Backend health check  
- `GET /docs` — Swagger API documentation  

Authentication and RAG-related endpoints will be documented after implementation and testing.

## Development Roadmap

### Phase 1 — Project foundation

- Repository structure
- Backend project setup
- Python virtual environment
- FastAPI application
- Configuration management
- Modular API routing
- API versioning
- Logging
- CORS configuration
- Health-check endpoint

### Phase 2 — Database foundation

- Docker Compose configuration
- PostgreSQL container
- pgvector-enabled database
- SQLAlchemy integration
- Database session management
- Alembic configuration
- Initial migration
- User model

### Phase 3 — Authentication

- Password hashing and verification
- JWT generation utility
- Authentication schemas
- User service foundation
- Registration API
- Login API
- JWT validation
- Protected user endpoint
- Authentication tests

### Phase 4 — Document ingestion

- Document model
- Document upload API
- File validation
- PDF parsing
- DOCX parsing
- Text extraction
- Text cleaning
- Document metadata storage

### Phase 5 — RAG pipeline

- Chunking strategy
- Embedding generation
- Vector storage
- Semantic retrieval
- Hybrid retrieval
- Metadata filtering
- Reranking
- Context building
- LLM response generation
- Source citations

### Phase 6 — Conversation and memory

- Conversation model
- Message history
- Working memory
- Long-term memory
- Context-aware conversations

### Phase 7 — Application platform

- Next.js frontend
- Authentication interface
- Document management interface
- Chat interface
- Streaming responses
- Voice interaction
- Multiple LLM providers

### Phase 8 — Quality and deployment

- Unit tests and integration tests
- Authentication tests
- RAG evaluation
- Backend Docker image
- CI/CD
- Monitoring
- Production deployment

## Security

- Passwords are stored as hashes, not plain text.
- JWT tokens will be used to protect authenticated endpoints.
- Environment variables and secrets must not be committed.
- User documents and vector data will be isolated per user or workspace.
- File type, size, and content validation will be added during document ingestion.

## Project Goals

The final platform is intended to provide:

- Secure private-document question answering
- Source-grounded AI responses
- Configurable retrieval strategies
- Conversation memory
- Multiple LLM provider support
- Voice-based interaction
- Modular and maintainable backend architecture
- Production-oriented deployment and monitoring

## License

This project is licensed under the MIT License.