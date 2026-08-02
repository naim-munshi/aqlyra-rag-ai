from collections.abc import Sequence

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
    validate_embedding_vector,
)
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
    EmbeddingRecord,
)


class EmbeddingDimensionError(Exception):
    """Raised when provider and database dimensions differ."""


class EmbeddingBatchError(Exception):
    """Raised when provider output does not match its input batch."""


def _batched(
    chunks: Sequence[DocumentChunk],
    batch_size: int,
) -> list[list[DocumentChunk]]:
    return [
        list(
            chunks[
                start:
                start + batch_size
            ]
        )
        for start in range(
            0,
            len(chunks),
            batch_size,
        )
    ]


def create_chunk_embeddings(
    db: Session,
    chunks: Sequence[DocumentChunk],
    provider: EmbeddingProvider | None = None,
) -> list[EmbeddingRecord]:
    if not chunks:
        return []

    active_provider = (
        provider
        or create_configured_embedding_provider()
    )

    provider_info = active_provider.info

    if (
        provider_info.dimension
        != EMBEDDING_DIMENSION
    ):
        raise EmbeddingDimensionError(
            "Embedding provider dimension "
            f"{provider_info.dimension} does not match "
            f"database dimension {EMBEDDING_DIMENSION}"
        )

    chunk_ids = [
        chunk.id
        for chunk in chunks
    ]

    if len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError(
            "Duplicate chunks were supplied "
            "for embedding"
        )

    db.execute(
        delete(EmbeddingRecord).where(
            EmbeddingRecord.chunk_id.in_(
                chunk_ids
            ),
            EmbeddingRecord.provider_name
            == provider_info.provider_name,
            EmbeddingRecord.model_name
            == provider_info.model_name,
        )
    )

    embedding_records: list[
        EmbeddingRecord
    ] = []

    for chunk_batch in _batched(
        chunks=chunks,
        batch_size=(
            provider_info.max_batch_size
        ),
    ):
        texts = [
            chunk.embedding_content
            for chunk in chunk_batch
        ]

        vectors = (
            active_provider.embed_documents(
                texts
            )
        )

        if len(vectors) != len(chunk_batch):
            raise EmbeddingBatchError(
                "Embedding provider returned "
                "an unexpected number of vectors"
            )

        for chunk, vector in zip(
            chunk_batch,
            vectors,
            strict=True,
        ):
            validate_embedding_vector(
                vector=vector,
                expected_dimension=(
                    EMBEDDING_DIMENSION
                ),
            )

            record = EmbeddingRecord(
                chunk_id=chunk.id,
                provider_name=(
                    provider_info.provider_name
                ),
                model_name=(
                    provider_info.model_name
                ),
                dimension=(
                    provider_info.dimension
                ),
                embedding=list(vector),
                content_hash=(
                    chunk.content_hash
                ),
                input_token_count=(
                    chunk.token_count
                ),
                estimated_cost_usd=0.0,
                embedding_metadata={
                    "chunk_role": (
                        chunk.chunk_role
                    ),
                    "chunk_level": (
                        chunk.chunk_level
                    ),
                    "strategy_version": (
                        chunk.strategy_version
                    ),
                    "source_label": (
                        chunk.source_label
                    ),
                    "provider_name": (
                        provider_info.provider_name
                    ),
                    "model_name": (
                        provider_info.model_name
                    ),
                },
            )

            embedding_records.append(
                record
            )

    db.add_all(embedding_records)

    return embedding_records
