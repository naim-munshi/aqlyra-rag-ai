import logging
from fastapi import FastAPI

from app.api.router import api_router
from app.config.settings import settings
from app.services.knowledge_index_queue import KnowledgeIndexWorker
from app.services.web_research_capability import public_web_research_status

_knowledge_worker = KnowledgeIndexWorker()
from app.middleware.auth_body_limit import AuthenticationBodyLimitMiddleware
from app.middleware.cors import setup_cors
from app.middleware.observability import (
    setup_request_observability,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production Grade RAG Platform",
    docs_url=(
        None
        if settings.is_production
        else "/docs"
    ),
    redoc_url=(
        None
        if settings.is_production
        else "/redoc"
    ),
    openapi_url=(
        None
        if settings.is_production
        else "/openapi.json"
    ),
)

setup_request_observability(app)
setup_cors(app)
# Outer ASGI ingress check prevents direct Render requests from bypassing
# the bounded Vercel authentication proxies.
app.add_middleware(AuthenticationBodyLimitMiddleware)

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "running",
        "version": settings.VERSION,
    }

@app.on_event("startup")
def start_knowledge_index_worker() -> None:
    # Existing FastAPI service can process the durable queue without
    # adding a new deployment or requiring a user to hold an HTTP request.
    # Non-secret operator evidence: a configured API key is NOT a live provider PASS.
    logging.getLogger(__name__).info(
        "public_web_research_configuration=%s", public_web_research_status(),
    )
    if settings.KNOWLEDGE_BACKFILL_ON_STARTUP:
        # Bounded, owner-linked recovery of legacy 'uploaded' cloud docs.
        # Errors do not take down the chat backend.
        try:
            from app.database.connection import SessionLocal
            from app.services.knowledge_index_queue import (
                requeue_verified_legacy_cloud_documents,
            )
            with SessionLocal() as db:
                requeue_verified_legacy_cloud_documents(db, limit=10)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "knowledge_legacy_cloud_backfill status=FAIL error_type=%s",
                type(exc).__name__,
            )
    _knowledge_worker.start()
    if settings.KNOWLEDGE_SEMANTIC_BACKFILL_ON_STARTUP:
        # One-shot operator-only backfill; never block HTTP readiness.
        from threading import Thread
        def run_semantic_backfill() -> None:
            try:
                from app.database.connection import SessionLocal
                from app.services.knowledge_semantic_backfill import (
                    backfill_ready_semantic_embeddings,
                )
                with SessionLocal() as db:
                    backfill_ready_semantic_embeddings(db=db, limit=1)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "knowledge_semantic_backfill status=ERROR error_type=%s",
                    type(exc).__name__,
                )
        Thread(
            target=run_semantic_backfill,
            name="aqlyra-semantic-backfill", daemon=True,
        ).start()
    if settings.WEB_RESEARCH_CANARY_ON_STARTUP:
        # Daemon keeps live startup/health independent of upstream latency.
        from threading import Thread
        from app.services.web_research_live_canary import run_live_web_canary
        Thread(
            target=run_live_web_canary,
            name="aqlyra-public-web-canary",
            daemon=True,
        ).start()


@app.on_event("shutdown")
def stop_knowledge_index_worker() -> None:
    _knowledge_worker.stop()
