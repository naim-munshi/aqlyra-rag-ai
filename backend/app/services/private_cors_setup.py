"""One-shot authenticated Neon S3 CORS setup for private direct uploads.

Only modifies the existing bucket's CORS configuration; never reads,
lists, overwrites or deletes a single user object. Preserves all existing
rules while adding a rule scoped exclusively to the Aqlyra production
origin and PUT. Requires explicit boot flag by the service operator.
"""
from botocore.exceptions import ClientError

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


if __name__ == "__main__":
    try:
        configure_private_upload_cors()
        print("PRIVATE_S3_CORS=PASS", flush=True)
    except Exception:
        print("PRIVATE_S3_CORS=FAIL", flush=True)
        raise SystemExit(1)
