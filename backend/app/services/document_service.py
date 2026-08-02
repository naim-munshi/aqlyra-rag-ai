from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.storage_service import PendingUpload


class DuplicateDocumentError(Exception):
    """Raised when the same user uploads identical content twice."""


def _get_constraint_name(error: IntegrityError) -> str | None:
    """
    Return the PostgreSQL constraint name that caused
    an integrity error.
    """
    original_error = error.orig
    diagnostic = getattr(original_error, "diag", None)

    return getattr(
        diagnostic,
        "constraint_name",
        None,
    )


def get_document_by_checksum(
    db: Session,
    user_id: str,
    checksum_sha256: str,
) -> Document | None:
    statement = select(Document).where(
        Document.user_id == user_id,
        Document.checksum_sha256 == checksum_sha256,
    )

    return db.scalar(statement)


def create_document(
    db: Session,
    user_id: str,
    pending_upload: PendingUpload,
) -> Document:
    document = Document(
        user_id=user_id,
        original_filename=pending_upload.original_filename,
        stored_filename=pending_upload.stored_filename,
        storage_path=pending_upload.relative_storage_path,
        content_type=pending_upload.content_type,
        file_extension=pending_upload.file_extension,
        file_size=pending_upload.file_size,
        checksum_sha256=pending_upload.checksum_sha256,
        status="uploaded",
        requires_ocr=False,
    )

    db.add(document)

    try:
        db.commit()
        db.refresh(document)

        return document

    except IntegrityError as exc:
        db.rollback()

        constraint_name = _get_constraint_name(exc)

        if constraint_name == "uq_documents_user_checksum":
            raise DuplicateDocumentError(
                "This document has already been uploaded"
            ) from exc

        raise

    except Exception:
        db.rollback()
        raise


def list_user_documents(
    db: Session,
    user_id: str,
    limit: int,
    offset: int,
) -> tuple[list[Document], int]:
    documents_statement = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(
            Document.created_at.desc(),
            Document.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    count_statement = (
        select(func.count())
        .select_from(Document)
        .where(Document.user_id == user_id)
    )

    documents = list(
        db.scalars(documents_statement).all()
    )

    total = db.scalar(count_statement) or 0

    return documents, total


def get_user_document(
    db: Session,
    user_id: str,
    document_id: str,
) -> Document | None:
    statement = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )

    return db.scalar(statement)


def delete_document_record(
    db: Session,
    document: Document,
) -> None:
    try:
        db.delete(document)
        db.commit()

    except Exception:
        db.rollback()
        raise