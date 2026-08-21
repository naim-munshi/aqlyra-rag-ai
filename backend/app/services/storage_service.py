import codecs
import hashlib
import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config.settings import settings


class UploadValidationError(Exception):
    """Base exception for invalid document uploads."""


class UnsupportedFileTypeError(UploadValidationError):
    """Raised when the file extension is not supported."""


class InvalidFileContentError(UploadValidationError):
    """Raised when file content does not match its extension."""


class FileTooLargeError(UploadValidationError):
    """Raised when the uploaded file exceeds the configured limit."""


class EmptyFileError(UploadValidationError):
    """Raised when an uploaded file contains no data."""


@dataclass(frozen=True)
class PendingUpload:
    original_filename: str
    stored_filename: str
    relative_storage_path: str
    temporary_path: Path
    content_type: str
    file_extension: str
    file_size: int
    checksum_sha256: str


_CANONICAL_CONTENT_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    ".pptx": (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    ),
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


_OOXML_REQUIRED_FILES: dict[str, str] = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
    ".pptx": "ppt/presentation.xml",
}


_IMAGE_FORMAT_BY_EXTENSION: dict[str, str] = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
}


MAX_IMAGE_PIXELS = 40_000_000


def _upload_root() -> Path:
    root = settings.UPLOAD_DIR.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sanitize_original_filename(filename: str | None) -> str:
    if filename is None:
        raise UnsupportedFileTypeError(
            "The uploaded file has no filename"
        )

    normalized = unicodedata.normalize("NFKC", filename)
    basename = Path(normalized).name.strip()

    basename = basename.replace("\x00", "")
    basename = re.sub(
        r"[^A-Za-z0-9._ -]",
        "_",
        basename,
    )
    basename = re.sub(
        r"\s+",
        " ",
        basename,
    ).strip(" .")

    if not basename:
        raise UnsupportedFileTypeError(
            "The filename is invalid"
        )

    if len(basename) <= 255:
        return basename

    suffix = Path(basename).suffix

    if not suffix:
        return basename[:255]

    maximum_stem_length = (
        255 - len(suffix)
    )

    stem = basename[
        :-len(suffix)
    ].rstrip(" .")

    truncated_stem = stem[
        :maximum_stem_length
    ].rstrip(" .")

    if not truncated_stem:
        raise UnsupportedFileTypeError(
            "The filename is invalid"
        )

    return (
        f"{truncated_stem}{suffix}"
    )


def _get_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in settings.allowed_document_extensions:
        allowed = ", ".join(
            sorted(settings.allowed_document_extensions)
        )

        raise UnsupportedFileTypeError(
            "Unsupported file type. "
            f"Allowed extensions: {allowed}"
        )

    return extension


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as file:
        signature = file.read(5)

    if signature != b"%PDF-":
        raise InvalidFileContentError(
            "The file content is not a valid PDF"
        )


def _validate_ooxml(
    path: Path,
    extension: str,
) -> None:
    if not zipfile.is_zipfile(path):
        raise InvalidFileContentError(
            f"The file content is not a valid {extension} document"
        )

    required_file = _OOXML_REQUIRED_FILES[extension]

    try:
        with zipfile.ZipFile(path) as archive:
            archive_files = set(
                archive.namelist()
            )

    except (
        OSError,
        zipfile.BadZipFile,
    ) as exc:
        raise InvalidFileContentError(
            f"The file content is not a valid {extension} document"
        ) from exc

    if required_file not in archive_files:
        raise InvalidFileContentError(
            f"The file content does not match {extension}"
        )


def _validate_text(path: Path) -> None:
    decoder = codecs.getincrementaldecoder(
        "utf-8-sig"
    )(
        errors="strict"
    )

    try:
        with path.open("rb") as file:
            while True:
                chunk = file.read(
                    settings.UPLOAD_CHUNK_SIZE_BYTES
                )

                if not chunk:
                    break

                if b"\x00" in chunk:
                    raise InvalidFileContentError(
                        "The uploaded text file contains binary data"
                    )

                decoder.decode(chunk)

            decoder.decode(
                b"",
                final=True,
            )

    except UnicodeDecodeError as exc:
        raise InvalidFileContentError(
            "Text files must use UTF-8 encoding"
        ) from exc


def _validate_image(
    path: Path,
    extension: str,
) -> None:
    expected_format = (
        _IMAGE_FORMAT_BY_EXTENSION[extension]
    )

    try:
        with Image.open(path) as image:
            detected_format = (
                image.format or ""
            ).upper()

            if detected_format != expected_format:
                raise InvalidFileContentError(
                    "Image content does not match "
                    f"{extension}"
                )

            width, height = image.size

            if width < 1 or height < 1:
                raise InvalidFileContentError(
                    "Image dimensions are invalid"
                )

            if width * height > MAX_IMAGE_PIXELS:
                raise InvalidFileContentError(
                    "Image dimensions are too large"
                )

            image.verify()

    except InvalidFileContentError:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise InvalidFileContentError(
            "The uploaded file is not a valid image"
        ) from exc


def _validate_file_content(
    path: Path,
    extension: str,
) -> str:
    if extension == ".pdf":
        _validate_pdf(path)

    elif extension in _OOXML_REQUIRED_FILES:
        _validate_ooxml(
            path,
            extension,
        )

    elif extension in {
        ".txt",
        ".md",
        ".csv",
    }:
        _validate_text(path)

    elif extension in _IMAGE_FORMAT_BY_EXTENSION:
        _validate_image(
            path,
            extension,
        )

    else:
        raise UnsupportedFileTypeError(
            f"Unsupported extension: {extension}"
        )

    return _CANONICAL_CONTENT_TYPES[
        extension
    ]


async def save_upload_to_temporary_storage(
    upload: UploadFile,
    user_id: str,
) -> PendingUpload:
    original_filename = (
        _sanitize_original_filename(
            upload.filename
        )
    )

    extension = _get_extension(
        original_filename
    )

    upload_root = _upload_root()

    temporary_directory = (
        upload_root
        / ".tmp"
        / user_id
    )

    temporary_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        temporary_directory
        / f"{uuid4().hex}.part"
    )

    checksum = hashlib.sha256()
    total_size = 0

    try:
        with temporary_path.open(
            "xb"
        ) as output_file:
            while True:
                chunk = await upload.read(
                    settings.UPLOAD_CHUNK_SIZE_BYTES
                )

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > settings.max_upload_size_bytes:
                    raise FileTooLargeError(
                        "File size exceeds "
                        f"{settings.MAX_UPLOAD_SIZE_MB} MB"
                    )

                checksum.update(chunk)
                output_file.write(chunk)

        if total_size == 0:
            raise EmptyFileError(
                "The uploaded file is empty"
            )

        canonical_content_type = (
            _validate_file_content(
                temporary_path,
                extension,
            )
        )

        stored_filename = (
            f"{uuid4().hex}{extension}"
        )

        relative_path = (
            Path(user_id)
            / stored_filename
        )

        return PendingUpload(
            original_filename=original_filename,
            stored_filename=stored_filename,
            relative_storage_path=(
                relative_path.as_posix()
            ),
            temporary_path=temporary_path,
            content_type=canonical_content_type,
            file_extension=extension,
            file_size=total_size,
            checksum_sha256=checksum.hexdigest(),
        )

    except Exception:
        temporary_path.unlink(
            missing_ok=True
        )
        raise

    finally:
        await upload.close()


def finalize_pending_upload(
    pending_upload: PendingUpload,
) -> Path:
    root = _upload_root()

    final_path = (
        root
        / pending_upload.relative_storage_path
    ).resolve()

    try:
        final_path.relative_to(root)

    except ValueError as exc:
        raise RuntimeError(
            "Unsafe storage path detected"
        ) from exc

    final_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.replace(
        pending_upload.temporary_path,
        final_path,
    )

    return final_path


def discard_pending_upload(
    pending_upload: PendingUpload,
) -> None:
    pending_upload.temporary_path.unlink(
        missing_ok=True
    )


def delete_stored_file(
    relative_storage_path: str,
) -> None:
    root = _upload_root()

    file_path = (
        root
        / relative_storage_path
    ).resolve()

    try:
        file_path.relative_to(root)

    except ValueError as exc:
        raise RuntimeError(
            "Unsafe storage path detected"
        ) from exc

    file_path.unlink(
        missing_ok=True
    )

    parent = file_path.parent

    if parent != root:
        try:
            parent.rmdir()

        except OSError:
            pass

class StoredFileNotFoundError(Exception):
    """Raised when a persisted upload cannot be resolved."""


def resolve_stored_file_path(
    relative_storage_path: str,
) -> Path:
    root = _upload_root()

    file_path = (
        root
        / relative_storage_path
    ).resolve()

    try:
        file_path.relative_to(root)

    except ValueError as exc:
        raise StoredFileNotFoundError(
            "Unsafe stored file path"
        ) from exc

    if (
        not file_path.exists()
        or not file_path.is_file()
    ):
        raise StoredFileNotFoundError(
            "Stored file does not exist"
        )

    return file_path
