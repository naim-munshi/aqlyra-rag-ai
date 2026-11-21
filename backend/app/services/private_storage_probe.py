"""Opt-in private S3 diagnostic with only synthetic, isolated objects.

Never reads, lists or deletes an existing user document or artifact.
A successful probe confirms only a basic provider write/read/delete cycle;
it does not certify tenant IAM, browser upload or disaster recovery.
"""
from __future__ import annotations

import secrets
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config.settings import settings
from app.services.private_object_storage import _endpoint

_PREFIX = "ops/aqlyra-storage-probes/"
_LIMIT = 128


class PrivateStorageProbeError(Exception):
    """Sanitized operator-facing failure; never includes S3/credential details."""


def _s3(cfg):
    try:
        endpoint = _endpoint(cfg.AWS_ENDPOINT_URL_S3)
        if not all((
            cfg.AWS_ACCESS_KEY_ID,
            cfg.AWS_SECRET_ACCESS_KEY,
            cfg.AWS_REGION,
            cfg.OBJECT_STORAGE_BUCKET,
        )):
            raise PrivateStorageProbeError("Private storage is not configured")
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=cfg.AWS_REGION,
            aws_access_key_id=cfg.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=cfg.AWS_SECRET_ACCESS_KEY,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=8,
                retries={"max_attempts": 1},
            ),
        )
    except PrivateStorageProbeError:
        raise
    except Exception as exc:
        raise PrivateStorageProbeError("Private storage configuration unavailable") from exc


def _object_absent(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        meta = response.get("ResponseMetadata", {}) if isinstance(response, dict) else {}
        return error.get("Code") in ("404", "NoSuchKey", "NotFound") or meta.get("HTTPStatusCode") == 404
    return False


def run_private_storage_probe(*, cfg=settings, client=None) -> None:
    """A one-time, collision-resistant probe with best-effort isolated cleanup.

    Keep the storage feature switches OFF during this test. The only writes are
    to one fresh UUID-scoped diagnostic object, never documents/ or artifacts/.
    """
    bucket = cfg.OBJECT_STORAGE_BUCKET
    if not bucket or not bucket.isascii() or len(bucket) > 63:
        raise PrivateStorageProbeError("Private bucket configuration unavailable")

    s3 = client if client is not None else _s3(cfg)
    key = _PREFIX + str(uuid4()) + ".bin"
    payload = b"aqlyra-storage-probe-v1:" + secrets.token_bytes(48)

    written = False
    valid_read = False
    cleaned = False
    try:
        s3.put_object(
            Bucket=bucket, Key=key, Body=payload,
            ContentType="application/octet-stream",
        )
        written = True
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response.get("Body")
        try:
            if body is not None and int(response.get("ContentLength", -1)) == len(payload):
                received = body.read(_LIMIT + 1)
                valid_read = received == payload
        finally:
            if body is not None:
                body.close()
    except Exception:
        # No provider message, endpoint, key or credentials are emitted.
        pass
    finally:
        # Also attempt deletion when the PUT had an ambiguous failure; the UUID
        # cannot match any pre-existing user object.
        try:
            s3.delete_object(Bucket=bucket, Key=key)
            cleaned = _object_absent(s3, bucket, key)
        except Exception:
            cleaned = False

    if not (written and valid_read and cleaned):
        raise PrivateStorageProbeError("Private S3 probe failed")


if __name__ == "__main__":
    try:
        run_private_storage_probe()
        print("PRIVATE_S3_PROBE=PASS", flush=True)
    except Exception:
        print("PRIVATE_S3_PROBE=FAIL", flush=True)
        raise SystemExit(1)
