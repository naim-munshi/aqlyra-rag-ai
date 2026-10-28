#!/usr/bin/env python3
"""CI-only isolated HTTP S3 artifact rehearsal across fresh app processes.

NEVER connects to Neon S3. Hard-coded loopback Moto endpoint, fake AWS
credentials, disposable PostgreSQL CI fixture and synthetic content only.
An explicitly separate Python process verifies restart-surviving bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

ENDPOINT = "http://127.0.0.1:5000"
BUCKET = "aqlyra-disposable-ci-artifacts"
FORMATS = ("md", "pdf", "docx", "xlsx", "pptx")


class CiS3Blocked(ValueError):
    pass


def verify_disposable_scope() -> None:
    """Reject anything other than the GitHub-local test database and S3."""
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CI") != "true":
        raise CiS3Blocked("not inside an approved disposable CI job")
    db = os.environ.get("DATABASE_URL", "")
    if db.startswith("postgresql+psycopg://"):
        db = "postgresql://" + db[len("postgresql+psycopg://"):]
    parsed = urlsplit(db)
    if (
        parsed.scheme != "postgresql"
        or parsed.hostname not in ("localhost", "127.0.0.1")
        or parsed.port not in (None, 5432)
        or parsed.path != "/aqlyra_rag_ai"
        or parsed.username != "postgres"
        or parsed.fragment
    ):
        raise CiS3Blocked("not the isolated CI PostgreSQL database")


def initialize():
    """Only localhost Moto client, never any production S3 endpoint."""
    import boto3
    from botocore.config import Config
    from app.config.settings import settings
    from app.services import artifact_remote_storage as remote

    settings.ARTIFACT_REMOTE_STORAGE_ENABLED = True
    settings.PRIVATE_OBJECT_STORAGE_ENABLED = True
    settings.OBJECT_STORAGE_BUCKET = BUCKET
    settings.ARTIFACT_METADATA_HMAC_KEY = (
        "ci-only-isolated-s3-metadata-key-do-not-ever-use-in-production"
    )
    client = boto3.client(
        "s3", endpoint_url=ENDPOINT, region_name="us-east-1",
        aws_access_key_id="ci-isolated-no-real-key",
        aws_secret_access_key="ci-isolated-no-real-secret",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    remote._storage = lambda: client
    return client, remote


def run(phase: str, state_file: Path) -> None:
    verify_disposable_scope()
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp or not state_file.resolve().is_relative_to(
        Path(runner_temp).resolve()
    ) or state_file.is_symlink():
        raise CiS3Blocked("CI state must stay under RUNNER_TEMP")

    client, remote = initialize()
    if phase == "write":
        if state_file.exists():
            raise CiS3Blocked("refuse to overwrite existing state")
        client.create_bucket(Bucket=BUCKET)
        owner = str(uuid4())
        stranger = str(uuid4())
        records = []
        for kind in FORMATS:
            artifact = remote.create_artifact(
                user_id=owner, title="Isolated restart proof",
                kind=kind, content="# Disposable synthetic content only",
                provider_name="ci", source_document_ids=[], citation_count=0,
            )
            records.append({
                "id": artifact["id"], "format": kind,
                "size": artifact["size"],
            })
        if len(remote.list_artifacts(user_id=owner)) != len(FORMATS):
            raise CiS3Blocked("not all artifacts were published")
        state = {"owner": owner, "stranger": stranger, "records": records}
        # Secure from creation; no briefly world-readable state file.
        descriptor = os.open(
            state_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(state))
        print("CI_ARTIFACT_S3_HTTP_WRITE=PASS")
        print("CI_APP_PROCESS_RESTART=REQUIRED")
        return

    if not state_file.is_file():
        raise CiS3Blocked("missing CI state file")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if (set(state) != {"owner", "stranger", "records"}
            or len(state["records"]) != len(FORMATS)):
        raise CiS3Blocked("invalid CI state")

    owner, stranger = state["owner"], state["stranger"]
    if phase == "verify":
        if remote.list_artifacts(user_id=stranger):
            raise CiS3Blocked("cross-account artifact enumeration")
        found = remote.list_artifacts(user_id=owner)
        if len(found) != len(FORMATS):
            raise CiS3Blocked("artifacts did not survive process restart")
        for item in state["records"]:
            artifact_id = item["id"]
            own = remote.artifact_download(user_id=owner, artifact_id=artifact_id)
            if (own is None or own[1]["format"] != item["format"]
                    or len(own[0]) != item["size"]):
                raise CiS3Blocked("artifact did not survive or content differs")
            # The generated bytes must match their owner-bound signed metadata.
            meta = remote._metadata(client, owner, artifact_id)
            if not meta or hashlib.sha256(own[0]).hexdigest() != meta["sha256"]:
                raise CiS3Blocked("restarted artifact integrity mismatch")
            if remote.read_artifact(user_id=stranger, artifact_id=artifact_id):
                raise CiS3Blocked("cross-owner artifact metadata leaked")
            if remote.artifact_download(user_id=stranger, artifact_id=artifact_id):
                raise CiS3Blocked("cross-owner artifact binary leaked")
        report = remote.audit_owner_inventory(user_id=owner)
        if report != {
            "complete_records": 5, "missing_binaries": 0,
            "invalid_metadata": 0, "orphan_binaries": 0,
            "unexpected_keys": 0, "total_objects": 10,
        }:
            raise CiS3Blocked("owner S3 inventory reconciliation failed")
        print("CI_ARTIFACT_S3_HTTP_RESTART_READ=PASS")
        print("CI_ARTIFACT_S3_HTTP_OWNER_ISOLATION=PASS")
        print("CI_ARTIFACT_S3_HTTP_INTEGRITY=PASS")
        return

    if phase == "cleanup":
        for item in state["records"]:
            if not remote.delete_artifact(
                user_id=owner, artifact_id=item["id"]
            ):
                raise CiS3Blocked("CI S3 deletion failed")
        if remote.list_artifacts(user_id=owner):
            raise CiS3Blocked("CI S3 artifact list not empty after deletion")
        if remote.audit_owner_inventory(user_id=owner)["total_objects"] != 0:
            raise CiS3Blocked("CI S3 residual objects")
        state_file.unlink()
        print("CI_ARTIFACT_S3_HTTP_CLEANUP=PASS")
        print("LIVE_NEON_S3=NOT_TOUCHED")
        return
    raise CiS3Blocked("invalid CI phase")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", choices=("write", "verify", "cleanup"), required=True)
    p.add_argument("--state-file", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        run(args.phase, args.state_file)
    except Exception:
        # Never echo S3 endpoint credentials, object keys, titles, or contents.
        print("CI_ARTIFACT_S3_HTTP=BLOCKED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
