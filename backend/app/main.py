from fastapi import FastAPI

from app.api.router import api_router
from app.config.settings import settings
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