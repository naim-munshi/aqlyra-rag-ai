from io import BytesIO
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
import app.services.document_processing_service as processing_service


PASSWORD = "UploadSecurityPass123!"


def create_auth_headers(
    client: TestClient,
    *,
    suffix: str,
) -> dict[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": suffix,
            "email": f"{suffix}@example.com",
            "password": PASSWORD,
        },
    )

    assert register.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"{suffix}@example.com",
            "password": PASSWORD,
        },
    )

    assert login.status_code == 200

    token = login.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


def upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
    content: bytes,
    content_type: str,
):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                content,
                content_type,
            ),
        },
    )


def assert_no_documents(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/documents",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def stored_files() -> list[Path]:
    root = settings.UPLOAD_DIR

    if not root.exists():
        return []

    return [
        path
        for path in root.rglob("*")
        if path.is_file()
    ]


def make_fake_ooxml() -> bytes:
    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<Types></Types>",
        )

    return buffer.getvalue()


def make_jpeg() -> bytes:
    buffer = BytesIO()

    image = Image.new(
        "RGB",
        (32, 32),
        "white",
    )

    image.save(
        buffer,
        format="JPEG",
    )

    return buffer.getvalue()


def test_zero_byte_upload_is_rejected_cleanly(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-empty",
    )

    response = upload(
        client,
        headers,
        filename="empty.md",
        content=b"",
        content_type="text/markdown",
    )

    assert response.status_code == 400

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_unsupported_executable_is_rejected_cleanly(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-exe",
    )

    response = upload(
        client,
        headers,
        filename="payload.exe",
        content=b"MZ-not-an-allowed-document",
        content_type=(
            "application/octet-stream"
        ),
    )

    assert response.status_code == 415

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_fake_pdf_is_rejected_before_database_write(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-fake-pdf",
    )

    response = upload(
        client,
        headers,
        filename="fake.pdf",
        content=b"NOT-A-PDF",
        content_type="application/pdf",
    )

    assert response.status_code == 400

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_fake_docx_is_rejected_before_database_write(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-fake-docx",
    )

    response = upload(
        client,
        headers,
        filename="fake.docx",
        content=make_fake_ooxml(),
        content_type=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml."
            "document"
        ),
    )

    assert response.status_code == 400

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_binary_text_is_rejected(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-binary-text",
    )

    response = upload(
        client,
        headers,
        filename="binary.txt",
        content=b"hello\x00world",
        content_type="text/plain",
    )

    assert response.status_code == 400

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_invalid_utf8_text_is_rejected(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-invalid-utf8",
    )

    response = upload(
        client,
        headers,
        filename="invalid.txt",
        content=b"\xff\xfe\xfa",
        content_type="text/plain",
    )

    assert response.status_code == 400

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_image_extension_mismatch_is_rejected(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-image-mismatch",
    )

    response = upload(
        client,
        headers,
        filename="actually-jpeg.png",
        content=make_jpeg(),
        content_type="image/png",
    )

    assert response.status_code == 400

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_oversized_upload_is_rejected_without_residue(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-oversized",
    )

    payload = (
        b"a"
        * (
            settings.max_upload_size_bytes
            + 1
        )
    )

    response = upload(
        client,
        headers,
        filename="oversized.md",
        content=payload,
        content_type="text/markdown",
    )

    assert response.status_code == 413

    assert_no_documents(
        client,
        headers,
    )

    assert stored_files() == []


def test_path_traversal_filename_is_sanitized(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-traversal",
    )

    response = upload(
        client,
        headers,
        filename="../../../../outside.md",
        content=b"# Safe content",
        content_type=(
            "application/x-msdownload"
        ),
    )

    assert response.status_code == 201

    payload = response.json()

    assert (
        payload["original_filename"]
        == "outside.md"
    )

    assert (
        payload["content_type"]
        == "text/markdown"
    )

    document_id = payload["id"]

    db_session.expire_all()

    document = db_session.scalar(
        select(Document).where(
            Document.id == document_id
        )
    )

    assert document is not None

    root = (
        settings.UPLOAD_DIR
        .expanduser()
        .resolve()
    )

    stored_path = (
        root / document.storage_path
    ).resolve()

    stored_path.relative_to(root)

    assert stored_path.is_file()


def test_long_supported_filename_preserves_extension(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-long-name",
    )

    filename = (
        ("a" * 300)
        + ".md"
    )

    response = upload(
        client,
        headers,
        filename=filename,
        content=b"# Long filename document",
        content_type="text/markdown",
    )

    assert response.status_code == 201, (
        response.status_code,
        response.text,
    )

    payload = response.json()

    assert len(
        payload["original_filename"]
    ) <= 255

    assert (
        payload["original_filename"]
        .endswith(".md")
    )


def test_processing_failure_rolls_back_partial_state_and_retries(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="upload-processing-rollback",
    )

    upload_response = upload(
        client,
        headers,
        filename="rollback.md",
        content=(
            b"# Rollback test\n\n"
            b"Processing must be atomic."
        ),
        content_type="text/markdown",
    )

    assert upload_response.status_code == 201

    document_id = (
        upload_response.json()["id"]
    )

    original_create_embeddings = (
        processing_service
        .create_chunk_embeddings
    )

    def fail_embedding_creation(
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "forced embedding failure"
        )

    monkeypatch.setattr(
        processing_service,
        "create_chunk_embeddings",
        fail_embedding_creation,
    )

    failed_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert failed_response.status_code == 500

    failed_document = client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )

    assert failed_document.status_code == 200

    failed_payload = (
        failed_document.json()
    )

    assert (
        failed_payload["status"]
        == "failed"
    )

    assert failed_payload[
        "error_message"
    ]

    units_response = client.get(
        (
            "/api/v1/documents/"
            f"{document_id}/units"
        ),
        headers=headers,
    )

    assert units_response.status_code == 200
    assert units_response.json()["total"] == 0
    assert units_response.json()["items"] == []

    db_session.expire_all()

    chunk_count = db_session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id
        )
    )

    assert chunk_count == 0

    monkeypatch.setattr(
        processing_service,
        "create_chunk_embeddings",
        original_create_embeddings,
    )

    retry_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert retry_response.status_code == 200

    retry_payload = retry_response.json()

    assert retry_payload["status"] == "ready"
    assert retry_payload["word_count"] > 0

    retry_units = client.get(
        (
            "/api/v1/documents/"
            f"{document_id}/units"
        ),
        headers=headers,
    )

    assert retry_units.status_code == 200
    assert retry_units.json()["total"] > 0
