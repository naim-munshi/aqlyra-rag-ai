"""One-shot authenticated Neon S3 CORS setup for private direct uploads.

Only modifies the existing bucket's CORS configuration; never reads,
lists, overwrites or deletes a single user object. Preserves all existing
rules while adding a rule scoped exclusively to the Aqlyra production
origin and PUT. Requires explicit boot flag by the service operator.
"""
from botocore.exceptions import ClientError
from uuid import uuid4
import requests

from app.config.settings import settings
from app.services.private_object_storage import _client

_ORIGIN = "https://aqlyra-ai.vercel.app"
_RULE_ID = "aqlyra-private-upload-production-v1"


def configure_private_upload_cors(*, storage=None, cfg=settings) -> None:
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED or not cfg.OBJECT_STORAGE_BUCKET:
        raise RuntimeError("Private storage not enabled")
    client = storage or _client(cfg)
    bucket = cfg.OBJECT_STORAGE_BUCKET
    try:
        existing = client.get_bucket_cors(Bucket=bucket).get("CORSRules", [])
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in {"NoSuchCORSConfiguration", "NoSuchCORS", "404"}:
            raise RuntimeError("Unable to inspect private upload CORS") from None
        existing = []
    if not isinstance(existing, list):
        raise RuntimeError("Unexpected private upload CORS configuration")
    desired = {
        "ID": _RULE_ID,
        "AllowedOrigins": [_ORIGIN],
        "AllowedMethods": ["PUT"],
        "AllowedHeaders": ["content-type"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 600,
    }
    rules = [x for x in existing if x.get("ID") != _RULE_ID]
    rules.append(desired)
    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={"CORSRules": rules},
    )
    verified = client.get_bucket_cors(Bucket=bucket).get("CORSRules", [])
    if not any(
        item.get("ID") == _RULE_ID and
        item.get("AllowedOrigins") == [_ORIGIN] and
        "PUT" in item.get("AllowedMethods", [])
        for item in verified
    ):
        raise RuntimeError("Private upload CORS verification failed")


def verify_browser_preflight(*, storage=None, cfg=settings) -> None:
    """Real HTTPS OPTIONS preflight on a private, never-written synthetic key.

    No object is uploaded. Signed URLs stay in process memory and are
    never logged, sent to a browser, or retained on disk.
    """
    if not cfg.PRIVATE_OBJECT_STORAGE_ENABLED:
        raise RuntimeError("Private storage unavailable")
    client = storage or _client(cfg)
    key = f"ops/aqlyra-cors-probes/{uuid4()}.txt"
    try:
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": cfg.OBJECT_STORAGE_BUCKET,
                "Key": key,
                "ContentType": "text/plain",
            },
            ExpiresIn=60,
            HttpMethod="PUT",
        )
        response = requests.options(
            url,
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
            timeout=9,
            allow_redirects=False,
        )
        # Status and header PRESENCE are safe for operator diagnostics.
        # Never emit URL, signature, bucket, credentials or provider body.
        if (
            response.status_code not in (200, 204)
            or response.headers.get("Access-Control-Allow-Origin") != _ORIGIN
            or "PUT" not in response.headers.get("Access-Control-Allow-Methods", "")
        ):
            print(
                f"PRIVATE_S3_PREFLIGHT_DIAG=status_{response.status_code}"
                f";origin_{int(response.headers.get('Access-Control-Allow-Origin') == _ORIGIN)}"
                f";put_{int('PUT' in response.headers.get('Access-Control-Allow-Methods', ''))}",
                flush=True,
            )
            raise RuntimeError("Browser private upload preflight failed")
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            print(f"PRIVATE_S3_PREFLIGHT_DIAG=exception_{type(exc).__name__}", flush=True)
        raise RuntimeError("Private upload CORS preflight unavailable") from None


if __name__ == "__main__":
    try:
        configure_private_upload_cors()
        print("PRIVATE_S3_CORS=PASS", flush=True)
        verify_browser_preflight()
        print("PRIVATE_S3_CORS_PREFLIGHT=PASS", flush=True)
    except Exception:
        print("PRIVATE_S3_CORS_OR_PREFLIGHT=FAIL", flush=True)
        raise SystemExit(1)
