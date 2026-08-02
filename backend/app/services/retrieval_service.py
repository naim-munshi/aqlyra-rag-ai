from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import (
    EmbeddingProvider,
    create_configured_embedding_provider,
    validate_embedding_vector,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import (
    EMBEDDING_DIMENSION,
    EmbeddingRecord,
)
from app.retrieval.types import (
    RetrievalHit,
    RetrievalProviderError,
    RetrievalQuery,
)


def search_similar_chunks(
    db: Session,
    query: RetrievalQuery,
    provider: EmbeddingProvider | None = None,
) -> list[RetrievalHit]:
    active_provider = (
        provider
        or create_configured_embedding_provider()
    )

    provider_info = active_provider.info

    if (
        provider_info.dimension
        != EMBEDDING_DIMENSION
    ):
        raise RetrievalProviderError(
            "Embedding provider dimension "
            f"{provider_info.dimension} "
            "does not match database dimension "
            f"{EMBEDDING_DIMENSION}"
        )

    query_vector = active_provider.embed_query(
        query.text
    )

    validate_embedding_vector(
        vector=query_vector,
        expected_dimension=EMBEDDING_DIMENSION,
    )

    cosine_distance = (
        EmbeddingRecord.embedding.cosine_distance(
            query_vector
        )
    )

    statement = (
        select(
            DocumentChunk,
            Document,
            cosine_distance.label(
                "cosine_distance"
            ),
        )
        .join(
            EmbeddingRecord,
            EmbeddingRecord.chunk_id
            == DocumentChunk.id,
        )
        .join(
            Document,
            Document.id
            == DocumentChunk.document_id,
        )
        .where(
            Document.user_id
            == query.user_id,
            Document.status
            == "ready",
            EmbeddingRecord.provider_name
            == provider_info.provider_name,
            EmbeddingRecord.model_name
            == provider_info.model_name,
            EmbeddingRecord.dimension
            == provider_info.dimension,
        )
    )

    if query.document_ids:
        statement = statement.where(
            Document.id.in_(
                query.document_ids
            )
        )

    if query.chunk_roles:
        statement = statement.where(
            DocumentChunk.chunk_role.in_(
                query.chunk_roles
            )
        )

    if query.min_similarity is not None:
        maximum_distance = (
            1.0
            - query.min_similarity
        )

        statement = statement.where(
            cosine_distance
            <= maximum_distance
        )

    statement = (
        statement
        .order_by(
            cosine_distance.asc(),
            DocumentChunk.chunk_index.asc(),
            DocumentChunk.id.asc(),
        )
        .limit(query.top_k)
    )

    rows = db.execute(
        statement
    ).all()

    hits: list[RetrievalHit] = []

    for chunk, document, distance in rows:
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
            RetrievalHit(
                chunk_id=chunk.id,
                document_id=document.id,
                original_filename=(
                    document.original_filename
                ),
                parent_chunk_id=(
                    chunk.parent_chunk_id
                ),
                chunk_role=chunk.chunk_role,
                chunk_level=chunk.chunk_level,
                chunk_index=chunk.chunk_index,
                source_label=(
                    chunk.source_label
                ),
                section_path=tuple(
                    chunk.section_path or []
                ),
                content=chunk.content,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                similarity_score=similarity,
                cosine_distance=(
                    numeric_distance
                ),
                metadata=dict(
                    chunk.chunk_metadata or {}
                ),
            )
        )

    return hits
