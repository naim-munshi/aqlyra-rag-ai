import hashlib
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import app_logger
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


class MemoryEmbeddingError(Exception):
    pass


class MemoryEmbeddingValidationError(
    MemoryEmbeddingError
):
    pass


class MemoryEmbeddingDimensionError(
    MemoryEmbeddingError
):
    pass


def _content_hash(
    content: str,
) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def _batched(
    memories: Sequence[Memory],
    batch_size: int,
) -> list[list[Memory]]:
    return [
        list(
            memories[
                start:
                start + batch_size
            ]
        )
        for start in range(
            0,
            len(memories),
            batch_size,
        )
    ]


def index_memory_embeddings(
    *,
    db: Session,
    user_id: str,
    memory_ids: Sequence[str],
    provider: EmbeddingProvider | None = None,
) -> list[MemoryEmbedding]:
    cleaned_user_id = user_id.strip()

    if not cleaned_user_id:
        raise MemoryEmbeddingValidationError(
            "user_id cannot be empty"
        )

    if isinstance(
        memory_ids,
        (str, bytes),
    ):
        raise MemoryEmbeddingValidationError(
            "memory_ids must be a sequence "
            "of memory identifiers"
        )

    cleaned_ids = tuple(
        memory_id.strip()
        for memory_id in memory_ids
        if memory_id.strip()
    )

    if not cleaned_ids:
        return []

    if len(set(cleaned_ids)) != len(
        cleaned_ids
    ):
        raise MemoryEmbeddingValidationError(
            "memory_ids cannot contain duplicates"
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
        raise MemoryEmbeddingDimensionError(
            "Embedding provider dimension "
            f"{provider_info.dimension} "
            "does not match memory vector "
            f"dimension {EMBEDDING_DIMENSION}"
        )

    statement = select(Memory).where(
        Memory.user_id == cleaned_user_id,
        Memory.id.in_(cleaned_ids),
    )

    owned_memories = list(
        db.scalars(statement).all()
    )

    memories_by_id = {
        memory.id: memory
        for memory in owned_memories
    }

    if len(memories_by_id) != len(
        cleaned_ids
    ):
        raise MemoryEmbeddingValidationError(
            "One or more memories were not found"
        )

    memories = [
        memories_by_id[memory_id]
        for memory_id in cleaned_ids
    ]

    try:
        prepared: list[
            tuple[Memory, list[float]]
        ] = []

        # Generate and validate every vector before
        # replacing any persisted vector index.
        for memory_batch in _batched(
            memories=memories,
            batch_size=(
                provider_info.max_batch_size
            ),
        ):
            texts = [
                memory.content
                for memory in memory_batch
            ]

            vectors = (
                active_provider.embed_documents(
                    texts
                )
            )

            if len(vectors) != len(
                memory_batch
            ):
                raise MemoryEmbeddingValidationError(
                    "Embedding provider returned "
                    "an unexpected number of vectors"
                )

            for memory, vector in zip(
                memory_batch,
                vectors,
                strict=True,
            ):
                validate_embedding_vector(
                    vector=vector,
                    expected_dimension=(
                        EMBEDDING_DIMENSION
                    ),
                )

                prepared.append(
                    (
                        memory,
                        list(vector),
                    )
                )

        records = [
            MemoryEmbedding(
                memory_id=memory.id,
                provider_name=(
                    provider_info.provider_name
                ),
                model_name=(
                    provider_info.model_name
                ),
                dimension=(
                    provider_info.dimension
                ),
                embedding=vector,
                content_hash=_content_hash(
                    memory.content
                ),
                input_token_count=0,
                estimated_cost_usd=0.0,
                embedding_metadata={
                    "source": "personal_memory",
                    "memory_kind": memory.kind,
                    "provider_name": (
                        provider_info.provider_name
                    ),
                    "model_name": (
                        provider_info.model_name
                    ),
                },
            )
            for memory, vector in prepared
        ]

        db.execute(
            delete(
                MemoryEmbedding
            ).where(
                MemoryEmbedding.memory_id.in_(
                    cleaned_ids
                ),
                MemoryEmbedding.provider_name
                == provider_info.provider_name,
                MemoryEmbedding.model_name
                == provider_info.model_name,
            )
        )

        db.add_all(records)
        db.commit()

    except Exception:
        db.rollback()
        raise

    for record in records:
        db.refresh(record)

    return records


def index_memory_embeddings_best_effort(
    *,
    db: Session,
    user_id: str,
    memory_ids: Sequence[str],
    provider: EmbeddingProvider | None = None,
) -> list[MemoryEmbedding]:
    try:
        return index_memory_embeddings(
            db=db,
            user_id=user_id,
            memory_ids=memory_ids,
            provider=provider,
        )

    except Exception:
        db.rollback()

        app_logger.exception(
            "Personal memory embedding "
            "indexing failed: "
            f"memory_count={len(memory_ids)}"
        )

        return []
