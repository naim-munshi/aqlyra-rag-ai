"""Offline-only validation of an age-encrypted offsite recovery bundle.

NEVER connects to, drops, truncates or restores a production database.
Runs with a decryption identity held by the operator OFF GitHub/Neon;
streams decrypted evidence to pg_restore --list or tar hash validation,
without writing private plaintext to disk.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


class InvalidBackup(Exception):
    pass


def _digest(path):
    value = sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            value.update(data)
    return value.hexdigest()


def verify_encrypted_files(directory, report):
    if report.get("format") != 1:
        raise InvalidBackup("Unsupported bundle version")
    required = {"postgres.dump.age", "cloud-objects.tar.age"}
    if set(report.get("components", {})) != required:
        raise InvalidBackup("Missing encrypted components")
    for name in required:
        file = directory / name
        evidence = report["components"][name]
        if not file.is_file() or file.stat().st_size != evidence["size"]:
            raise InvalidBackup("Encrypted component size mismatch")
        if _digest(file) != evidence["sha256"]:
            raise InvalidBackup("Encrypted component checksum mismatch")


def _decrypt_pipe(encrypted, identity):
    return subprocess.Popen(
        ["age", "-d", "-i", str(identity), str(encrypted)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )


def _pinned_pg18_image():
    image = os.environ.get("AQ_PG18_IMAGE", "")
    if not re.fullmatch(r"postgres:18@sha256:[0-9a-f]{64}", image):
        raise InvalidBackup("Immutable PostgreSQL 18 verifier image is required")
    return image


def verify_database(directory, identity):
    age = _decrypt_pipe(directory / "postgres.dump.age", identity)
    try:
        if age.stdout is None:
            raise InvalidBackup("Database decryption pipe unavailable")
        inspect = subprocess.Popen(
            ["docker", "run", "--rm", "-i", _pinned_pg18_image(),
             "pg_restore", "--list"],
            stdin=age.stdout, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        age.stdout.close()
        if inspect.wait() != 0 or age.wait() != 0:
            raise InvalidBackup("PostgreSQL custom-format archive is invalid")
    finally:
        if age.poll() is None:
            age.kill()
        age.wait()


def verify_objects(directory, identity, report):
    age = _decrypt_pipe(directory / "cloud-objects.tar.age", identity)
    try:
        if age.stdout is None:
            raise InvalidBackup("Object decryption pipe unavailable")
        with tarfile.open(fileobj=age.stdout, mode="r|") as tar:
            first = tar.next()
            if first is None or first.name != "manifest.json" or first.size > 5_000_000:
                raise InvalidBackup("Invalid object manifest")
            handle = tar.extractfile(first)
            if handle is None:
                raise InvalidBackup("Cannot read object manifest")
            manifest = json.loads(handle.read(first.size))
            if manifest.get("format") != 1:
                raise InvalidBackup("Unsupported object manifest")
            expected = {
                row["archive_name"]: row
                for row in manifest.get("objects", [])
            }
            if len(expected) != len(manifest.get("objects", [])):
                raise InvalidBackup("Duplicate archived object")
            if len(expected) != report["object_count"]:
                raise InvalidBackup("Object count differs from published marker")
            checked = set()
            for member in tar:
                if not member.isfile() or not re.fullmatch(
                    r"objects/[0-9a-f]{64}\.bin", member.name
                ):
                    raise InvalidBackup("Unsafe or unexpected archive entry")
                row = expected.get(member.name)
                if row is None or member.name in checked or member.size != row["size"]:
                    raise InvalidBackup("Wrong archived object metadata")
                body = tar.extractfile(member)
                if body is None:
                    raise InvalidBackup("Missing archived object bytes")
                digest = sha256()
                size = 0
                for block in iter(lambda: body.read(1024 * 1024), b""):
                    size += len(block)
                    digest.update(block)
                if size != row["size"] or digest.hexdigest() != row["sha256"]:
                    raise InvalidBackup("Archived cloud object changed")
                checked.add(member.name)
            if checked != set(expected):
                raise InvalidBackup("Incomplete private object archive")
        age.stdout.close()
        if age.wait() != 0:
            raise InvalidBackup("Object archive could not be decrypted")
    finally:
        if age.poll() is None:
            age.kill()
        age.wait()


def main():
    location = Path(os.environ["AQ_OFFSITE_BUNDLE_DIRECTORY"]).resolve()
    identity = Path(os.environ["AQ_OFFSITE_AGE_IDENTITY_PATH"]).resolve()
    if not identity.is_file() or not location.is_dir():
        raise InvalidBackup("Local archive and offline identity are required")
    if identity.is_relative_to(location):
        raise InvalidBackup("Never store the offline age private key beside backup artifacts")
    report = json.loads((location / "COMPLETE.json").read_text(encoding="utf-8"))
    verify_encrypted_files(location, report)
    verify_database(location, identity)
    verify_objects(location, identity, report)
    print("AQLYRA_OFFSITE_BUNDLE_OFFLINE_VERIFY=PASS")
    print("OBJECT_COUNT=" + str(report["object_count"]))
    print("LIVE_DB_RESTORE=NOT_ATTEMPTED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("AQLYRA_OFFSITE_BUNDLE_OFFLINE_VERIFY=FAILED")
        print("SAFE_FAILURE_CLASS=" + type(exc).__name__)
        sys.exit(1)
