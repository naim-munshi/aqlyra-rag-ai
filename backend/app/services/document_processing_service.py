from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now_naive
from app.config.settings import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_unit import DocumentUnit
from app.parsers import parse_document
from app.services.chunk_service import (
    create_document_chunks,
)
from app.services.embedding_service import (
    create_chunk_embeddings,
)
from app.embeddings import (
    EmbeddingProviderQuotaError, EmbeddingProviderRequestError,
    EmbeddingValidationError, EmbeddingProviderNotFoundError,
)
from app.services.embedding_service import EmbeddingDimensionError, EmbeddingBatchError


class DocumentProcessingConflictError(Exception):
    """Raised when a document cannot currently be processed."""


class StoredDocumentNotFoundError(Exception):
    """Raised when the stored document file cannot be found."""


def _resolve_stored_document_path(
    relative_storage_path: str,
) -> Path:
    upload_root = (
        settings.UPLOAD_DIR
        .expanduser()
        .resolve()
    )

    document_path = (
        upload_root
        / relative_storage_path
    ).resolve()

    try:
        document_path.relative_to(
            upload_root
        )

    except ValueError as exc:
        raise StoredDocumentNotFoundError(
            "Unsafe document storage path"
        ) from exc

    if not document_path.exists():
        raise StoredDocumentNotFoundError(
            "The stored document file "
            "does not exist"
        )

    if not document_path.is_file():
        raise StoredDocumentNotFoundError(
            "The stored document path "
            "is not a file"
        )

    return document_path


def _mark_document_failed(
    db: Session,
    document_id: str,
    error: Exception,
) -> None:
    db.rollback()

    failed_document = db.get(
        Document,
        document_id,
    )

    if failed_document is None:
        return

    # Avoid leaking provider tokens/URLs into user-visible document status.
    error_message = type(error).__name__[:120]

    failed_document.status = "failed"
    failed_document.error_message = (
        error_message
    )
    failed_document.processed_at = (
        utc_now_naive()
    )

    try:
        db.commit()

    except Exception:
        db.rollback()


def process_document(
    db: Session,
    document: Document,
    *,
    verified_source_path: Path | None = None,
    claimed_for_worker: bool = False,
) -> Document:
    if document.status == "ready":
        raise DocumentProcessingConflictError(
            "Document has already been processed"
        )

    if document.status in {"processing", "queued"} and not (
        claimed_for_worker and document.status == "processing"
    ):
        raise DocumentProcessingConflictError(
            f"Document is currently {document.status}"
        )

    document_id = document.id

    document.status = "processing"
    document.error_message = None

    try:
        db.commit()
        db.refresh(document)

        if document.storage_path.startswith("cloud://"):
            if verified_source_path is None or not verified_source_path.is_file():
                raise StoredDocumentNotFoundError(
                    "Verified private cloud document source is required"
                )
            document_path = verified_source_path
        else:
            if verified_source_path is not None:
                raise DocumentProcessingConflictError(
                    "External source must not override a local document"
                )
            document_path = _resolve_stored_document_path(
                document.storage_path
            )

        parse_result = parse_document(
            path=document_path,
            file_extension=(
                document.file_extension
            ),
        )

        db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id
                == document_id
            )
        )

        db.execute(
            delete(DocumentUnit).where(
                DocumentUnit.document_id
                == document_id
            )
        )

        db.flush()

        extracted_units = [
            DocumentUnit(
                document_id=document_id,
                unit_index=(
                    unit.unit_index
                ),
                unit_type=(
                    unit.unit_type
                ),
                source_label=(
                    unit.source_label
                ),
                content=unit.content,
                content_hash=(
                    unit.content_hash
                ),
                char_count=(
                    unit.char_count
                ),
                word_count=(
                    unit.word_count
                ),
                unit_metadata={
                    **unit.metadata,
                    "parser_name": (
                        parse_result
                        .parser_name
                    ),
                },
            )
            for unit in parse_result.units
        ]

        db.add_all(extracted_units)
        db.flush()

        chunks = create_document_chunks(
            db=db,
            document=document,
            units=extracted_units,
        )

        db.flush()

        # Deterministic hash embeddings are test vectors, not semantic
        # search. In production, use real embeddings when available;
        # retain lexical indexing if the external provider is unavailable.
        use_lexical_only = (
            settings.KNOWLEDGE_LEXICAL_FALLBACK_ENABLED
            and settings.EMBEDDING_PROVIDER == "deterministic"
        )
        if not use_lexical_only:
            try:
                create_chunk_embeddings(db=db, chunks=chunks)
            except (EmbeddingProviderRequestError, EmbeddingProviderQuotaError):
                if not settings.KNOWLEDGE_LEXICAL_FALLBACK_ENABLED:
                    raise
                use_lexical_only = True

        if use_lexical_only:
            # No fabricated vectors. PostgreSQL FTS can search real parsed
            # chunks while preserving the actual filename/page citations.
            for chunk in chunks:
                chunk.chunk_metadata = {
                    **(chunk.chunk_metadata or {}),
                    "retrieval_mode": "lexical_only",
                }

        document.page_count = (
            parse_result.page_count
        )
        document.word_count = (
            parse_result.word_count
        )
        document.parsing_quality_score = (
            parse_result.quality_score
        )
        document.requires_ocr = (
            parse_result.requires_ocr
        )
        document.status = "ready"
        document.error_message = None
        document.processed_at = (
            utc_now_naive()
        )

        db.commit()
        db.refresh(document)

        return document

    except Exception as exc:
        _mark_document_failed(
            db=db,
            document_id=document_id,
            error=exc,
        )

        raise


def list_document_units(
    db: Session,
    document_id: str,
    limit: int,
    offset: int,
) -> tuple[list[DocumentUnit], int]:
    units_statement = (
        select(DocumentUnit)
        .where(
            DocumentUnit.document_id
            == document_id
        )
        .order_by(
            DocumentUnit.unit_index.asc()
        )
        .offset(offset)
        .limit(limit)
    )

    count_statement = (
        select(func.count())
        .select_from(DocumentUnit)
        .where(
            DocumentUnit.document_id
            == document_id
        )
    )

    units = list(
        db.scalars(
            units_statement
        ).all()
    )

    total = (
        db.scalar(count_statement)
        or 0
    )

    return units, total
