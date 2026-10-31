"""Authenticated private-by-token semantic worker. No file or DB access."""
import hmac
import logging
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from semantic_worker.model import DIMENSION, MODEL, get_encoder

logger = logging.getLogger("aqlyra.semantic_worker")


class EmbeddingRequest(BaseModel):
    mode: Literal["query", "passage"]
    texts: list[str] = Field(min_length=1, max_length=8)


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    vectors: list[list[float]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    token = os.environ.get("SEMANTIC_WORKER_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("SEMANTIC_WORKER_TOKEN must be set with high entropy")
    get_encoder()  # fail closed if model absent; health only after loaded.
    logger.info("semantic_worker_ready model=%s dimension=%s", MODEL, DIMENSION)
    yield


app = FastAPI(
    title="Aqlyra Private Semantic Encoder",
    docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ready", "model": MODEL, "dimension": DIMENSION}


@app.post("/v1/embed", response_model=EmbeddingResponse)
def embed(
    body: EmbeddingRequest,
    authorization: str | None = Header(default=None),
):
    secret = os.environ.get("SEMANTIC_WORKER_TOKEN", "")
    if not secret or not hmac.compare_digest(
        authorization or "", "Bearer " + secret,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if any(not text.strip() or len(text) > 6000 for text in body.texts):
        raise HTTPException(status_code=422, detail="Invalid bounded text input")
    try:
        vectors = get_encoder().encode(body.texts, body.mode)
    except Exception as exc:
        logger.error("semantic_inference_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Semantic inference unavailable") from None
    return EmbeddingResponse(model=MODEL, dimension=DIMENSION, vectors=vectors)
