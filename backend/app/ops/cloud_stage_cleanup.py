"""Operator-only cloud stage cleanup.

By default performs a read-only dry run. Destructive action needs two
independent command-line confirmations and a configured private bucket.
Do not schedule on a free sleeping web service.
"""
import argparse
import json
from app.config.settings import settings
from app.database.connection import SessionLocal
from app.services.cloud_stage_cleanup import cleanup_stale_staging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--grace-hours", type=int, default=24)
    args = parser.parse_args()
    if args.apply and args.confirm != "EXPIRED_STAGING_ONLY":
        parser.error("--apply requires --confirm EXPIRED_STAGING_ONLY")
    if not settings.PRIVATE_OBJECT_STORAGE_ENABLED:
        parser.error("Private object storage is disabled")
    with SessionLocal() as db:
        result = cleanup_stale_staging(
            db=db, cfg=settings, dry_run=not args.apply,
            grace_seconds=args.grace_hours * 3600, limit=args.limit,
        )
    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "eligible": result.eligible,
        "deleted": result.deleted,
        "failed": result.failed,
    }))


if __name__ == "__main__":
    main()
