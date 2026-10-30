#!/usr/bin/env python3
"""CI-only HTTP S3 proof for original private RAG document byte durability.

Uses synthetic text only, fake S3 credentials, hard-coded local Moto server,
and a disposable GitHub Actions PostgreSQL fixture for safety gating.
No Neon endpoint is contacted; NO production feature flag is toggled.
Each phase must execute in a SEPARATE Python process. The S3 service stays
alive, simulating application restarts (not S3/provider restarts).
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
from ci_artifact_s3_roundtrip import verify_disposable_scope  # noqa: E402

BUCKET = "aqlyra-ci-original-private-docs"
ENDPOINT = "http://127.0.0.1:5000"
# Stable synthetic bytes, never actual user documents.
CONTENT = "Aqlyra synthetic private RAG source — 検証 — বাংলা".encode("utf-8")


class PrivateS3RehearsalBlocked(ValueError):
    """Never attach provider exception text, paths, payloads or URLs."""


def check_state_path(path: Path) -> None:
    runner = os.environ.get("RUNNER_TEMP")
    if (
        not runner or path.is_symlink()
        or not path.resolve().is_relative_to(Path(runner).resolve())
    ):
        raise PrivateS3RehearsalBlocked("state outside disposable CI directory")


def client_and_cfg():
    import boto3
    from botocore.config import Config
    from app.config.settings import Settings

    # Config intentionally has Neon-shaped URL so production endpoint
    # validation remains strict; only the injected boto3 client reaches Moto.
    cfg = Settings(
        _env_file=None, PRIVATE_OBJECT_STORAGE_ENABLED=True,
        AWS_ENDPOINT_URL_S3=(
            "https://br-private-example.storage.c-2.us-east-2.aws.neon.tech"
        ),
        AWS_REGION="us-east-2",
        AWS_ACCESS_KEY_ID="ci-fake-id",
        AWS_SECRET_ACCESS_KEY="ci-fake-not-a-secret",
        OBJECT_STORAGE_BUCKET=BUCKET,
    )
    client = boto3.client(
        "s3", region_name="us-east-1", endpoint_url=ENDPOINT,
        aws_access_key_id="ci-fake-id",
        aws_secret_access_key="ci-fake-not-a-secret",
        config=Config(
            signature_version="s3v4", s3={"addressing_style": "path"},
        ),
    )
    return client, cfg


def inventory(client, prefix: str) -> int:
    total = 0
    continuation = None
    while True:
        params = {"Bucket": BUCKET, "Prefix": prefix, "MaxKeys": 100}
        if continuation is not None:
            params["ContinuationToken"] = continuation
        result = client.list_objects_v2(**params)
        total += len(result.get("Contents", []))
        if not result.get("IsTruncated"):
            return total
        continuation = result.get("NextContinuationToken")
        if not isinstance(continuation, str) or not continuation:
            raise PrivateS3RehearsalBlocked("invalid S3 inventory cursor")


def run(phase: str, path: Path) -> None:
    verify_disposable_scope()
    check_state_path(path)
    from app.services.private_object_storage import (
        PrivateObjectStorageError,
        assert_owned_key,
        object_key,
        verified_private_temporary_file,
    )
    from app.services.private_object_promotion import (
        assert_owned_final_key,
        final_object_key,
        promote_verified_private_upload,
        verify_existing_final_private_object,
    )
    client, cfg = client_and_cfg()
    digest = hashlib.sha256(CONTENT).hexdigest()
    if phase == "write":
        if path.exists():
            raise PrivateS3RehearsalBlocked("existing state file")
        client.create_bucket(Bucket=BUCKET)
        owner, stranger = str(uuid4()), str(uuid4())
        stage = object_key(
            owner_id=owner, object_id=str(uuid4()), extension=".txt",
        )
        final = final_object_key(
            owner_id=owner, object_id=str(uuid4()), extension=".txt",
        )
        # An untrusted browser PUT may only target a staging prefix.
        client.put_object(
            Bucket=BUCKET, Key=stage, Body=CONTENT, ContentType="text/plain",
        )
        promoted = promote_verified_private_upload(
            owner_id=owner, staging_key=stage,
            expected_size=len(CONTENT), expected_sha256=digest,
            cfg=cfg, client=client, final_key=final,
        )
        if (
            promoted.key != final or promoted.content_type != "text/plain"
            or promoted.sha256 != digest or promoted.size_bytes != len(CONTENT)
            or inventory(client, f"documents/{owner}/") != 1
            or inventory(client, f"final/documents/{owner}/") != 1
        ):
            raise PrivateS3RehearsalBlocked("private promotion mismatch")
        state = {
            "owner": owner, "stranger": stranger, "stage": stage,
            "final": final, "length": len(CONTENT), "sha256": digest,
        }
        # Secure at file creation, not after the file has been written.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(state, out)
        print("CI_ORIGINAL_S3_HTTP_PROMOTION=PASS")
        print("CI_APPLICATION_PROCESS_RESTART=REQUIRED")
        return

    if not path.is_file() or path.stat().st_mode & 0o077:
        raise PrivateS3RehearsalBlocked("insecure or missing state file")
    state = json.loads(path.read_text(encoding="utf-8"))
    if set(state) != {"owner", "stranger", "stage", "final", "length", "sha256"}:
        raise PrivateS3RehearsalBlocked("invalid state contract")
    owner, stranger = state["owner"], state["stranger"]
    stage, final = state["stage"], state["final"]
    if (
        owner == stranger or assert_owned_key(owner_id=owner, key=stage) != ".txt"
        or assert_owned_final_key(owner_id=owner, key=final) != ".txt"
        or state["length"] != len(CONTENT) or state["sha256"] != digest
    ):
        raise PrivateS3RehearsalBlocked("invalid original document identity")

    if phase == "verify":
        # New client and new Python process: final object outlives the app.
        final_obj = verify_existing_final_private_object(
            owner_id=owner, final_key=final,
            expected_size=len(CONTENT), expected_sha256=digest,
            cfg=cfg, client=client,
        )
        if final_obj.key != final:
            raise PrivateS3RehearsalBlocked("final object disappeared")
        for check in (
            lambda: assert_owned_final_key(owner_id=stranger, key=final),
            lambda: assert_owned_key(owner_id=stranger, key=stage),
            lambda: verify_existing_final_private_object(
                owner_id=stranger, final_key=final,
                expected_size=len(CONTENT), expected_sha256=digest,
                cfg=cfg, client=client,
            ),
        ):
            try:
                check()
            except PrivateObjectStorageError:
                pass
            else:
                raise PrivateS3RehearsalBlocked("owner boundary broken")
        if (
            inventory(client, f"documents/{stranger}/")
            or inventory(client, f"final/documents/{stranger}/")
        ):
            raise PrivateS3RehearsalBlocked("cross-owner object leakage")

        # A browser can replay its 120s staging PUT, but it must NEVER be
        # able to replace the already-promoted, server-owned final object.
        client.put_object(
            Bucket=BUCKET, Key=stage,
            Body=b"MALICIOUS STAGING REPLAY", ContentType="text/plain",
        )
        try:
            with verified_private_temporary_file(
                owner_id=owner, key=stage,
                expected_size=len(CONTENT), expected_sha256=digest,
                cfg=cfg, client=client,
            ):
                raise PrivateS3RehearsalBlocked("tampered staging accepted")
        except PrivateObjectStorageError:
            pass
        verify_existing_final_private_object(
            owner_id=owner, final_key=final,
            expected_size=len(CONTENT), expected_sha256=digest,
            cfg=cfg, client=client,
        )
        if (
            inventory(client, f"documents/{owner}/") != 1
            or inventory(client, f"final/documents/{owner}/") != 1
        ):
            raise PrivateS3RehearsalBlocked("restart inventory drift")
        print("CI_ORIGINAL_S3_HTTP_RESTART_READ=PASS")
        print("CI_ORIGINAL_S3_HTTP_OWNER_ISOLATION=PASS")
        print("CI_ORIGINAL_S3_HTTP_STAGE_REPLAY_DEFENSE=PASS")
        return

    if phase == "cleanup":
        client.delete_object(Bucket=BUCKET, Key=stage)
        client.delete_object(Bucket=BUCKET, Key=final)
        if inventory(client, "") != 0:
            raise PrivateS3RehearsalBlocked("residual private objects")
        path.unlink()
        print("CI_ORIGINAL_S3_HTTP_CLEANUP=PASS")
        print("LIVE_NEON_S3=NOT_TOUCHED")
        return
    raise PrivateS3RehearsalBlocked("invalid phase")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("write", "verify", "cleanup"))
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        run(args.phase, args.state_file)
    except Exception:
        # Never print exception detail, URLs, credentials or raw file content.
        print("CI_ORIGINAL_S3_HTTP=BLOCKED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
