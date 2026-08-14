from fastapi import APIRouter

from app.api.auth import (
    router as auth_router,
)
from app.api.conversations import (
    router as conversations_router,
)
from app.api.documents import (
    router as documents_router,
)
from app.api.embedding_indexing import (
    router as embedding_indexing_router,
)
from app.api.rag import (
    router as rag_router,
)
from app.api.retrieval import (
    router as retrieval_router,
)
from app.api.users import (
    router as users_router,
)
from app.api.v1.health import (
    router as health_router,
)


api_router = APIRouter()

api_router.include_router(
    health_router
)

api_router.include_router(
    auth_router
)

api_router.include_router(
    users_router
)

api_router.include_router(
    conversations_router
)

api_router.include_router(
    documents_router
)

api_router.include_router(
    embedding_indexing_router
)

api_router.include_router(
    retrieval_router
)

api_router.include_router(
    rag_router
)
