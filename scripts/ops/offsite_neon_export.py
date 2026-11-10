"""Opt-in, client-side encrypted PostgreSQL+private cloud-object export.

Runs ONLY in an explicitly approved GitHub Actions environment, never on the
user-facing Render worker. Source content is never written unencrypted to
the Actions filesystem and never copied to a provider-managed GitHub artifact.

The offsite destination must be an INDEPENDENT S3 account/bucket. The offline
age decryption identity must NOT be stored in Actions or Neon.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


_KEY = re.compile(
    r"final/documents/([0-9a-f-]{36})/([0-9a-f-]{36})"
    r"(\.(?:pdf|docx|xlsx|pptx|txt|md|csv|png|jpg|jpeg|webp))\Z"
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")


class BackupRefused(Exception):
    """A safe stop; no incomplete export is published."""


def _key_and_label(*, key: str, owner: str, expected_sha: str, size: int):
    match = _KEY.fullmatch(key)
    if not match or match.group(1) != owner or not _SHA.fullmatch(expected_sha):
        raise BackupRefused("A completed object does not have a safe owner binding")
    if size < 0 or size > 100 * 1024 * 1024:
        raise BackupRefused("A private object exceeds the bounded backup size")
    return "objects/" + hashlib.sha256(key.encode()).hexdigest() + ".bin"


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BackupRefused("Offsite backup configuration is incomplete")
    return value


def _preflight():
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("AQ_OFFSITE_BACKUP_ENABLED") != "yes"
        or os.environ.get("AQ_OFFSITE_BACKUP_CONFIRMED") != "offsite-v1"
    ):
        raise BackupRefused("Offsite backup was not explicitly authorized")
    recipient = _required("AQ_AGE_PUBLIC_RECIPIENT")
    if not recipient.startswith("age1") or len(recipient) < 50:
        raise BackupRefused("Only an offline-generated age X25519 public recipient is allowed")
    dest = _required("AQ_OFFSITE_BUCKET")
    source = _required("AQ_SOURCE_BUCKET")
    if not _BUCKET.fullmatch(dest) or not _BUCKET.fullmatch(source):
        raise BackupRefused("Invalid private/offsite bucket name")
    if dest == source:
        raise BackupRefused("Offsite destination cannot be the private source bucket")
    for field in (
        "AQ_SOURCE_S3_ENDPOINT", "AQ_SOURCE_ACCESS_KEY_ID",
        "AQ_SOURCE_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY", "AQ_NEON_DATABASE_URL",
    ):
        _required(field)
    if not os.environ["AQ_SOURCE_S3_ENDPOINT"].startswith("https://"):
        raise BackupRefused("Source storage must use HTTPS")
    if not os.environ.get("AQ_OFFSITE_ENDPOINT", "https://s3.amazonaws.com").startswith("https://"):
        raise BackupRefused("Destination storage must use HTTPS")
    return recipient, source, dest


def _age_encrypt_stream(input_handle, output: Path, recipient: str):
    with output.open("xb") as encrypted:
        age = subprocess.Popen(
            ["age", "-r", recipient],
            stdin=input_handle, stdout=encrypted, stderr=subprocess.DEVNULL,
        )
        rc = age.wait()
    if rc != 0 or output.stat().st_size == 0:
        raise BackupRefused("Public-key encryption failed")


def _dump_pg18_to_encrypted_file(output: Path, recipient: str):
    # Docker receives PGDATABASE by NAME, not by inline secret value.
    # pg_dump 18 matches the verified source major version 18.
    env = {**os.environ, "PGDATABASE": _required("AQ_NEON_DATABASE_URL")}
    command = [
        "docker", "run", "--rm", "--network", "host",
        "-e", "PGDATABASE", "postgres:18", "pg_dump",
        "-Fc", "--no-owner", "--no-privileges",
    ]
    dump = subprocess.Popen(command, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env)
    try:
        if dump.stdout is None:
            raise BackupRefused("No database dump stream")
        _age_encrypt_stream(dump.stdout, output, recipient)
        dump.stdout.close()
        if dump.wait() != 0:
            raise BackupRefused("Production database export failed")
    finally:
        if dump.poll() is None:
            dump.kill()
            dump.wait()


class _VerifyingObjectReader:
    def __init__(self, body, expected_bytes: int):
        self.body = body
        self.remaining = expected_bytes
        self.sha = hashlib.sha256()

    def read(self, n=-1):
        if self.remaining == 0:
            return b""
        wanted = self.remaining if n < 0 else min(self.remaining, n)
        chunk = self.body.read(wanted)
        if not chunk:
            raise BackupRefused("Truncated private object stream")
        self.sha.update(chunk)
        self.remaining -= len(chunk)
        return chunk

    def verify(self, expected_sha: str):
        if self.remaining != 0 or self.sha.hexdigest() != expected_sha:
            raise BackupRefused("Private object checksum verification failed")


def _load_cloud_inventory():
    import psycopg

    sql = """SELECT i.final_object_key, i.user_id, i.expected_sha256,
                     i.expected_size
              FROM cloud_upload_intents AS i
              JOIN documents AS d
                ON d.id=i.document_id AND d.user_id=i.user_id
               AND d.checksum_sha256=i.expected_sha256
               AND d.file_size=i.expected_size
               AND d.storage_path='cloud://' || i.final_object_key
              WHERE i.status='completed' AND i.deleted_at IS NULL
                AND i.final_object_key IS NOT NULL
              ORDER BY i.id"""
    with psycopg.connect(_required("AQ_NEON_DATABASE_URL"), connect_timeout=15) as db:
        rows = db.execute(sql).fetchall()
    if len(rows) > 10000:
        raise BackupRefused("Too many completed cloud documents for a bounded backup")
    result = []
    total_bytes = 0
    seen = set()
    for key, owner, sha, size in rows:
        filename = _key_and_label(
            key=key, owner=owner, expected_sha=sha, size=int(size),
        )
        if filename in seen:
            raise BackupRefused("Repeated final object key")
        seen.add(filename)
        total_bytes += int(size)
        if total_bytes > 2 * 1024**3:
            raise BackupRefused("Offsite export exceeds the 2 GiB safety budget")
        result.append({
            "key": key, "owner": owner, "sha256": sha,
            "size": int(size), "archive_name": filename,
        })
    return result


def _objects_to_encrypted_tar(output: Path, recipient: str, inventory, source_s3, source_bucket):
    # Tar is written directly into age; plaintext is only in bounded memory.
    with output.open("xb") as encrypted:
        age = subprocess.Popen(
            ["age", "-r", recipient],
            stdin=subprocess.PIPE, stdout=encrypted,
            stderr=subprocess.DEVNULL,
        )
        try:
            if age.stdin is None:
                raise BackupRefused("Encryption pipe unavailable")
            with tarfile.open(fileobj=age.stdin, mode="w|") as archive:
                payload = json.dumps(
                    {"format": 1, "objects": inventory},
                    separators=(",", ":"), ensure_ascii=False,
                ).encode()
                manifest = tarfile.TarInfo("manifest.json")
                manifest.size = len(payload)
                manifest.mode = 0o600
                archive.addfile(manifest, io.BytesIO(payload))
                for record in inventory:
                    response = source_s3.get_object(
                        Bucket=source_bucket, Key=record["key"],
                    )
                    if response.get("ContentLength") != record["size"]:
                        raise BackupRefused("Private cloud size changed during backup")
                    reader = _VerifyingObjectReader(response["Body"], record["size"])
                    try:
                        entry = tarfile.TarInfo(record["archive_name"])
                        entry.size = record["size"]
                        entry.mode = 0o600
                        archive.addfile(entry, reader)
                        reader.verify(record["sha256"])
                    finally:
                        response["Body"].close()
            age.stdin.close()
            if age.wait() != 0:
                raise BackupRefused("Private object encryption failed")
        except Exception:
            if age.stdin:
                age.stdin.close()
            if age.poll() is None:
                age.kill()
            age.wait()
            raise


def main():
    recipient, source_bucket, dest_bucket = _preflight()
    import boto3

    source_s3 = boto3.client(
        "s3",
        endpoint_url=_required("AQ_SOURCE_S3_ENDPOINT"),
        aws_access_key_id=_required("AQ_SOURCE_ACCESS_KEY_ID"),
        aws_secret_access_key=_required("AQ_SOURCE_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AQ_SOURCE_REGION", "us-east-2"),
    )
    destination = boto3.client(
        "s3",
        endpoint_url=os.environ.get("AQ_OFFSITE_ENDPOINT") or None,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"aqlyra/backup-v1/{now}"
    # Scratch contains only ENCRYPTED archives. No raw SQL/object bytes.
    with tempfile.TemporaryDirectory(prefix="aqlyra-enc-") as name:
        root = Path(name)
        os.chmod(root, 0o700)
        db_archive = root / "postgres.dump.age"
        object_archive = root / "cloud-objects.tar.age"
        inventory = _load_cloud_inventory()
        _dump_pg18_to_encrypted_file(db_archive, recipient)
        _objects_to_encrypted_tar(
            object_archive, recipient, inventory, source_s3, source_bucket,
        )
        report = {
            "format": 1, "timestamp_utc": now, "object_count": len(inventory),
            "components": {},
        }
        for path in (db_archive, object_archive):
            with path.open("rb") as handle:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
            report["components"][path.name] = {
                "sha256": hasher.hexdigest(), "size": path.stat().st_size,
            }
        for path in (db_archive, object_archive):
            destination.upload_file(
                str(path), dest_bucket, prefix + "/" + path.name,
            )
        # Atomic publish marker last: no marker = incomplete attempt.
        destination.put_object(
            Bucket=dest_bucket,
            Key=prefix + "/COMPLETE.json",
            Body=(json.dumps(report, sort_keys=True) + "\n").encode(),
            ContentType="application/json",
        )
    print("AQLYRA_OFFSITE_ENCRYPTED_EXPORT=PASS")
    print("COMPONENTS=2")
    print("OBJECT_COUNT=" + str(len(inventory)))
    print("REQUIRES_OFFLINE_AGE_IDENTITY_FOR_RESTORE=true")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print exception detail: provider messages may include
        # bucket names, object identifiers or private connection strings.
        print("AQLYRA_OFFSITE_ENCRYPTED_EXPORT=FAILED")
        print("SAFE_FAILURE_CLASS=" + type(exc).__name__)
        sys.exit(1)
