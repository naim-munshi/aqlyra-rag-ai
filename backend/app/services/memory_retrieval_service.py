from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
    validate_embedding_vector,
)
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
)
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding


class MemoryRetrievalError(Exception):
    pass


class MemoryRetrievalValidationError(
    MemoryRetrievalError
):
    pass


class MemoryRetrievalProviderError(
    MemoryRetrievalError
):
    pass


@dataclass(frozen=True, slots=True)
class MemoryRetrievalHit:
    memory_id: str
    kind: str
    content: str
    importance: float
    confidence: float
    similarity_score: float
    cosine_distance: float


def retrieve_memories_for_user(
    *,
    db: Session,
    user_id: str,
    query_text: str,
    top_k: int = 5,
    min_similarity: float | None = None,
    provider: EmbeddingProvider | None = None,
) -> list[MemoryRetrievalHit]:
    cleaned_user_id = user_id.strip()
    cleaned_query = query_text.strip()

    if not cleaned_user_id:
        raise MemoryRetrievalValidationError(
            "user_id cannot be empty"
        )

    if not cleaned_query:
        raise MemoryRetrievalValidationError(
            "Memory retrieval query cannot be empty"
        )

    if not 1 <= top_k <= 50:
        raise MemoryRetrievalValidationError(
            "top_k must be between 1 and 50"
        )

    if (
        min_similarity is not None
        and not (
            -1.0
            <= min_similarity
            <= 1.0
        )
    ):
        raise MemoryRetrievalValidationError(
            "min_similarity must be between "
            "-1.0 and 1.0"
        )

    active_provider = (
        provider
        or create_configured_embedding_provider()
    )

    provider_info = active_provider.info

    if (
        provider_info.dimension
        != EMBEDDING_DIMENSION
    ):
        raise MemoryRetrievalProviderError(
            "Embedding provider dimension "
            f"{provider_info.dimension} "
            "does not match memory vector "
            f"dimension {EMBEDDING_DIMENSION}"
        )

    query_vector = (
        active_provider.embed_query(
            cleaned_query
        )
    )

    validate_embedding_vector(
        vector=query_vector,
        expected_dimension=(
            EMBEDDING_DIMENSION
        ),
    )

    cosine_distance = (
        MemoryEmbedding
        .embedding
        .cosine_distance(
            query_vector
        )
    )

    statement = (
        select(
            Memory,
            cosine_distance.label(
                "cosine_distance"
            ),
        )
        .join(
            MemoryEmbedding,
            MemoryEmbedding.memory_id
            == Memory.id,
        )
        .where(
            Memory.user_id
            == cleaned_user_id,
            Memory.is_active.is_(True),
            MemoryEmbedding.provider_name
            == provider_info.provider_name,
            MemoryEmbedding.model_name
            == provider_info.model_name,
            MemoryEmbedding.dimension
            == provider_info.dimension,
        )
    )

    if min_similarity is not None:
        maximum_distance = (
            1.0 - min_similarity
        )

        statement = statement.where(
            cosine_distance
            <= maximum_distance
        )

    statement = (
        statement
        .order_by(
            cosine_distance.asc(),
            Memory.importance.desc(),
            Memory.updated_at.desc(),
            Memory.id.asc(),
        )
        .limit(top_k)
    )

    rows = db.execute(
        statement
    ).all()

    hits: list[
        MemoryRetrievalHit
    ] = []

    for memory, distance in rows:
        numeric_distance = float(
            distance
        )

        similarity = max(
            -1.0,
            min(
                1.0,
                1.0 - numeric_distance,
            ),
        )

        hits.append(
            MemoryRetrievalHit(
                memory_id=memory.id,
                kind=memory.kind,
                content=memory.content,
                importance=memory.importance,
                confidence=memory.confidence,
                similarity_score=similarity,
                cosine_distance=(
                    numeric_distance
                ),
            )
        )

    return hits
