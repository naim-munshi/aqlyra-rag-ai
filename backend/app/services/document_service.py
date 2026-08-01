from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.storage_service import PendingUpload


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
    except Exception:
        db.rollback()
        raise

    return document


def list_user_documents(
    db: Session,
    user_id: str,
    limit: int,
    offset: int,
) -> tuple[list[Document], int]:
    documents_statement = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
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
    db.delete(document)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise