#!/usr/bin/env python3
"""Verify local Markdown links and fenced blocks without external dependencies."""

from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
EXTERNAL_PREFIXES = ("http:", "https:", "mailto:", "tel:", "data:")


def check_document(file_path: Path) -> list[str]:
    errors: list[str] = []
    lines = file_path.read_text(encoding="utf-8").splitlines()
    fence: str | None = None

    for number, line in enumerate(lines, start=1):
        match = FENCE_PATTERN.match(line)

        if match:
            delimiter = match.group(1)
            if fence is None:
                fence = delimiter
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence):
                fence = None
            continue

        if fence is not None:
            continue

        for link in LINK_PATTERN.finditer(line):
            raw = link.group(1).strip().split(" ", 1)[0]

            if not raw or raw.startswith("#"):
                continue

            if raw.lower().startswith(EXTERNAL_PREFIXES):
                continue

            target = unquote(raw.split("#", 1)[0])
            if not target:
                continue

            # Local link targets must stay within the repository.
            resolved = (file_path.parent / target).resolve()
            try:
                resolved.relative_to(REPOSITORY_ROOT)
            except ValueError:
                errors.append(f"{file_path}:{number}: link escapes repository")
                continue

            if not resolved.exists():
                errors.append(
                    f"{file_path}:{number}: missing local target: {raw}"
                )

    if fence is not None:
        errors.append(f"{file_path}: unclosed Markdown code fence")

    return errors


def main() -> int:
    tracked = subprocess.check_output(
        ["git", "ls-files", "--", "*.md"],
        cwd=REPOSITORY_ROOT,
        text=True,
    ).splitlines()

    errors: list[str] = []
    for path in tracked:
        source = REPOSITORY_ROOT / path
        if source.is_file():
            errors.extend(check_document(source))

    for error in errors:
        print(error, file=sys.stderr)

    print(f"Markdown files verified: {len(tracked)}; errors: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
