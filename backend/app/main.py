from fastapi import FastAPI

from app.api.router import api_router
from app.config.settings import settings
from app.core.logging import app_logger
from app.middleware.cors import setup_cors

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production Grade RAG Platform",
)

setup_cors(app)

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


@app.get("/")
async def root():
    app_logger.info("Root endpoint accessed")

    return {
        "project": settings.PROJECT_NAME,
        "status": "running",
        "version": settings.VERSION,
    }