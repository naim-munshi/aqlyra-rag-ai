import argparse
import asyncio
import secrets
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select

from app.database.connection import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.user import UserCreate
from app.services.document_processing_service import (
    process_document,
)
from app.services.document_service import (
    create_document,
    get_document_by_checksum,
)
from app.services.storage_service import (
    discard_pending_upload,
    finalize_pending_upload,
    save_upload_to_temporary_storage,
)
from app.services.user_service import (
    create_user,
    get_user_by_email,
)


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CORPUS_DIR = (
    ROOT
    / "evaluation"
    / "corpus"
)

BENCHMARK_EMAIL = (
    "retrieval-benchmark@aqlyra.dev"
)

BENCHMARK_USERNAME = (
    "retrieval_benchmark"
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed the reproducible Aqlyra "
            "retrieval benchmark corpus."
        )
    )

    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
    )

    return parser.parse_args()


async def ingest_document(
    *,
    db,
    user_id: str,
    path: Path,
) -> tuple[Document, str]:
    file_handle = path.open("rb")

    upload = UploadFile(
        filename=path.name,
        file=file_handle,
    )

    pending = (
        await save_upload_to_temporary_storage(
            upload=upload,
            user_id=user_id,
        )
    )

    existing = get_document_by_checksum(
        db=db,
        user_id=user_id,
        checksum_sha256=(
            pending.checksum_sha256
        ),
    )

    if existing is not None:
        discard_pending_upload(
            pending
        )

        if existing.status != "ready":
            existing = process_document(
                db=db,
                document=existing,
            )

        return existing, "reused"

    document: Document | None = None

    try:
        document = create_document(
            db=db,
            user_id=user_id,
            pending_upload=pending,
        )

        finalize_pending_upload(
            pending
        )

        document = process_document(
            db=db,
            document=document,
        )

        return document, "created"

    except Exception:
        discard_pending_upload(
            pending
        )

        if document is not None:
            db.rollback()

        raise


def count_document_chunks(
    *,
    db,
    document_id: str,
) -> int:
    statement = (
        select(func.count())
        .select_from(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id
        )
    )

    return int(
        db.scalar(statement)
        or 0
    )


async def async_main() -> None:
    args = parse_args()

    corpus_dir = (
        args.corpus_dir
        .expanduser()
        .resolve()
    )

    files = sorted(
        corpus_dir.glob("*.md")
    )

    if not files:
        raise RuntimeError(
            "No Markdown benchmark corpus "
            f"files found in {corpus_dir}"
        )

    with SessionLocal() as db:
        user = get_user_by_email(
            db,
            BENCHMARK_EMAIL,
        )

        if user is None:
            user = create_user(
                db=db,
                user_data=UserCreate(
                    username=(
                        BENCHMARK_USERNAME
                    ),
                    email=BENCHMARK_EMAIL,
                    password=(
                        secrets.token_urlsafe(24)
                    ),
                ),
            )

            user_state = "created"

        else:
            user_state = "reused"

        print(
            "Benchmark user:",
            user.id,
            f"({user_state})",
        )

        total_chunks = 0

        for path in files:
            document, state = (
                await ingest_document(
                    db=db,
                    user_id=user.id,
                    path=path,
                )
            )

            chunk_count = (
                count_document_chunks(
                    db=db,
                    document_id=document.id,
                )
            )

            total_chunks += chunk_count

            print(
                f"{path.name}: "
                f"{state}, "
                f"{document.status}, "
                f"{chunk_count} chunks"
            )

        ready_count = int(
            db.scalar(
                select(func.count())
                .select_from(Document)
                .where(
                    Document.user_id
                    == user.id,
                    Document.status
                    == "ready",
                )
            )
            or 0
        )

        print()
        print(
            "Ready documents:",
            ready_count,
        )

        print(
            "Total chunks:",
            total_chunks,
        )

        print()
        print(
            "BENCHMARK_USER_ID="
            f"{user.id}"
        )


def main() -> None:
    asyncio.run(
        async_main()
    )


if __name__ == "__main__":
    main()
