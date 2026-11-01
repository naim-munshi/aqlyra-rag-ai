"""Package only the existing Aqlyra voice runtime for LiveKit Cloud.

LiveKit's CLI reads `Dockerfile` from its build-context root. Aqlyra's API
uses `backend/Dockerfile`, while the dedicated worker uses
`backend/Dockerfile.voice`. Never let the cloud CLI deploy the API Dockerfile.
No environment files, uploads, database backups or credentials are copied.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def prepare_voice_context(target: Path, *, source: Path = BACKEND_ROOT) -> Path:
    source = source.resolve()
    target = target.resolve()
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("Voice cloud build context must be outside the backend source tree")
    if target.exists():
        raise FileExistsError("Voice cloud build directory must not already exist")

    required = (
        source / "Dockerfile.voice",
        source / "requirements.txt",
        source / "requirements-voice.txt",
        source / ".dockerignore",
        source / "app" / "voice" / "worker.py",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Missing voice packaging input: {path.name}")

    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source / "Dockerfile.voice", target / "Dockerfile")
    shutil.copy2(source / "requirements.txt", target / "requirements.txt")
    shutil.copy2(source / "requirements-voice.txt", target / "requirements-voice.txt")
    shutil.copy2(source / ".dockerignore", target / ".dockerignore")
    shutil.copytree(
        source / "app",
        target / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env", ".env.*"),
    )
    return target


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: prepare_livekit_context.py OUTPUT_DIRECTORY", file=sys.stderr)
        return 2
    try:
        prepare_voice_context(Path(sys.argv[1]))
    except (OSError, ValueError) as exc:
        print(f"voice_cloud_package=BLOCKED: {exc}", file=sys.stderr)
        return 1
    print("voice_cloud_package=PASS (packaged only; no agent deployed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
