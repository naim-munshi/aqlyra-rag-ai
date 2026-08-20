import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
)
from app.config.settings import settings
from app.main import app
from app.models.document import Document
from app.models.user import User


def _create_user(
    db: Session,
    *,
    suffix: str,
) -> User:
    user = User(
        email=(
            f"{suffix}@example.com"
        ),
        username=suffix,
        hashed_password=(
            "test-password-hash"
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _authenticate_as(
    user: User,
) -> None:
    app.dependency_overrides[
        get_current_user
    ] = lambda: user


def _create_document(
    db: Session,
    *,
    user: User,
    payload: bytes,
    write_file: bool,
) -> Document:
    token = uuid4().hex

    relative_path = (
        f"{user.id}/"
        f"{token}.txt"
    )

    if write_file:
        file_path = (
            settings.UPLOAD_DIR
            .expanduser()
            .resolve()
            / relative_path
        )

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.write_bytes(
            payload
        )

    document = Document(
        user_id=str(user.id),
        original_filename=(
            "attachment.txt"
        ),
        stored_filename=(
            f"{token}.txt"
        ),
        storage_path=relative_path,
        content_type="text/plain",
        file_extension=".txt",
        file_size=len(payload),
        checksum_sha256=(
            hashlib.sha256(
                payload
                + token.encode("utf-8")
            ).hexdigest()
        ),
        status="ready",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def test_owner_can_read_document_content(
    client: TestClient,
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        suffix="content-owner",
    )

    payload = (
        b"Aqlyra persisted attachment."
    )

    document = _create_document(
        db_session,
        user=user,
        payload=payload,
        write_file=True,
    )

    _authenticate_as(user)

    response = client.get(
        (
            "/api/v1/documents/"
            f"{document.id}/content"
        )
    )

    assert response.status_code == 200
    assert response.content == payload

    assert (
        response.headers[
            "content-type"
        ].startswith(
            "text/plain"
        )
    )

    assert (
        response.headers[
            "content-disposition"
        ].startswith(
            "inline"
        )
    )


def test_other_user_cannot_read_document_content(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = _create_user(
        db_session,
        suffix="content-private-owner",
    )

    other_user = _create_user(
        db_session,
        suffix="content-private-other",
    )

    document = _create_document(
        db_session,
        user=owner,
        payload=b"Private attachment.",
        write_file=True,
    )

    _authenticate_as(
        other_user
    )

    response = client.get(
        (
            "/api/v1/documents/"
            f"{document.id}/content"
        )
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Document not found"
    )


def test_missing_stored_file_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        suffix="content-missing",
    )

    document = _create_document(
        db_session,
        user=user,
        payload=b"Missing attachment.",
        write_file=False,
    )

    _authenticate_as(user)

    response = client.get(
        (
            "/api/v1/documents/"
            f"{document.id}/content"
        )
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Document content not found"
    )
