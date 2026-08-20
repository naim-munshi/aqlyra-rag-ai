from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.logging import app_logger
from app.database.connection import get_db
from app.models.user import User
from app.parsers import DocumentParsingError
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUnitListResponse,
)
from app.services.document_processing_service import (
    DocumentProcessingConflictError,
    StoredDocumentNotFoundError,
    list_document_units,
    process_document,
)
from app.services.document_service import (
    DuplicateDocumentError,
    create_document,
    delete_document_record,
    get_document_by_checksum,
    get_user_document,
    list_user_documents,
)
from app.services.storage_service import (
    EmptyFileError,
    FileTooLargeError,
    InvalidFileContentError,
    UnsupportedFileTypeError,
    delete_stored_file,
    discard_pending_upload,
    finalize_pending_upload,
    save_upload_to_temporary_storage,
)

from app.services.storage_service import (
    StoredFileNotFoundError,
    resolve_stored_file_path,
)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "PDF, DOCX, XLSX, PPTX, TXT, "
                "MD, or CSV document"
            )
        ),
    ],
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        pending_upload = (
            await save_upload_to_temporary_storage(
                upload=file,
                user_id=str(current_user.id),
            )
        )

    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_413_CONTENT_TOO_LARGE
            ),
            detail=str(exc),
        ) from exc

    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=str(exc),
        ) from exc

    except (
        InvalidFileContentError,
        EmptyFileError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    duplicate_document = get_document_by_checksum(
        db=db,
        user_id=str(current_user.id),
        checksum_sha256=(
            pending_upload.checksum_sha256
        ),
    )

    if duplicate_document is not None:
        discard_pending_upload(
            pending_upload
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "This document has already "
                    "been uploaded"
                ),
                "document_id": (
                    duplicate_document.id
                ),
            },
        )

    finalize_pending_upload(
        pending_upload
    )

    try:
        return create_document(
            db=db,
            user_id=str(current_user.id),
            pending_upload=pending_upload,
        )

    except DuplicateDocumentError as exc:
        delete_stored_file(
            pending_upload.relative_storage_path
        )

        existing_document = get_document_by_checksum(
            db=db,
            user_id=str(current_user.id),
            checksum_sha256=(
                pending_upload.checksum_sha256
            ),
        )

        detail: dict[str, str] = {
            "message": (
                "This document has already "
                "been uploaded"
            ),
        }

        if existing_document is not None:
            detail["document_id"] = (
                existing_document.id
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc

    except Exception:
        delete_stored_file(
            pending_upload.relative_storage_path
        )
        raise


@router.get(
    "",
    response_model=DocumentListResponse,
)
def read_documents(
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    documents, total = list_user_documents(
        db=db,
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
    )

    return DocumentListResponse(
        items=documents,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
)
def process_uploaded_document(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = get_user_document(
        db=db,
        user_id=str(current_user.id),
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        processed_document = process_document(
            db=db,
            document=document,
        )

        app_logger.info(
            f"Document processed: {document_id}"
        )

        return processed_document

    except DocumentProcessingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except StoredDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except DocumentParsingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc

    except Exception as exc:
        app_logger.exception(
            f"Unexpected document processing "
            f"error for {document_id}: {exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Document processing failed",
        ) from exc


@router.get(
    "/{document_id}/units",
    response_model=DocumentUnitListResponse,
)
def read_document_units(
    document_id: str,
    limit: Annotated[
        int,
        Query(ge=1, le=500),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> DocumentUnitListResponse:
    document = get_user_document(
        db=db,
        user_id=str(current_user.id),
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    units, total = list_document_units(
        db=db,
        document_id=document.id,
        limit=limit,
        offset=offset,
    )

    return DocumentUnitListResponse(
        document_id=document.id,
        document_status=document.status,
        items=units,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}/content",
    response_class=FileResponse,
)
def read_document_content(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = get_user_document(
        db=db,
        user_id=str(current_user.id),
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Document not found",
        )

    try:
        file_path = (
            resolve_stored_file_path(
                document.storage_path
            )
        )

    except StoredFileNotFoundError as exc:
        app_logger.warning(
            "Stored document content missing: "
            f"document_id={document.id}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Document content not found"
            ),
        ) from exc

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.original_filename,
        content_disposition_type="inline",
        headers={
            "Cache-Control": (
                "private, no-store"
            ),
            "X-Content-Type-Options": (
                "nosniff"
            ),
        },
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def read_document(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = get_user_document(
        db=db,
        user_id=str(current_user.id),
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> Response:
    document = get_user_document(
        db=db,
        user_id=str(current_user.id),
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    storage_path = document.storage_path

    delete_document_record(
        db=db,
        document=document,
    )

    delete_stored_file(
        storage_path
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
