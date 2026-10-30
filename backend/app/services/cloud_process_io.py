"""Temporary verified S3 source for a cloud Document parser."""
import hashlib
import tempfile
from contextlib import contextmanager
from pathlib import Path

from app.config.settings import settings
from app.services.cloud_document_access import verified_cloud_document_key
from app.services.private_object_storage import _client, PrivateObjectStorageError
from app.services.storage_service import _validate_file_content


@contextmanager
def cloud_processing_source(*, db, owner_id, document, store=None):
    key = verified_cloud_document_key(
        db=db, owner_id=owner_id, document=document,
    )
    if not 0 < document.file_size <= settings.max_upload_size_bytes:
        raise PrivateObjectStorageError("Invalid private document size")
    storage = store if store is not None else _client(settings)
    body = None
    tmp = None
    try:
        result = storage.get_object(
            Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key,
        )
        body = result["Body"]
        if int(result["ContentLength"]) != document.file_size:
            raise PrivateObjectStorageError("Private document size mismatch")
        tmp = tempfile.NamedTemporaryFile(
            prefix="aqlyra-cloud-", suffix=document.file_extension,
            delete=False,
        )
        total = 0
        digest = hashlib.sha256()
        with tmp:
            for chunk in body.iter_chunks(chunk_size=1048576):
                if not chunk:
                    continue
                total += len(chunk)
                if total > document.file_size:
                    raise PrivateObjectStorageError("Private file too large")
                digest.update(chunk)
                tmp.write(chunk)
        if total != document.file_size or digest.hexdigest() != document.checksum_sha256:
            raise PrivateObjectStorageError("Private file checksum mismatch")
        _validate_file_content(Path(tmp.name), document.file_extension)
        yield Path(tmp.name)
    except PrivateObjectStorageError:
        raise
    except Exception as exc:
        raise PrivateObjectStorageError("Private file processing unavailable") from exc
    finally:
        if body is not None and callable(getattr(body, "close", None)):
            body.close()
        if tmp is not None:
            Path(tmp.name).unlink(missing_ok=True)
