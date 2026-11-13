#!/usr/bin/env python3
"""Read-only safety preflight: reject fixed-name Docker containers from other projects.

Aqlyra uses fixed container names. Running a new Git worktree under a
different Compose project must not silently reuse or interfere with
the original checkout's containers and persistent database.
"""
from collections.abc import Callable
import subprocess
import sys


OWNED_NAMES = (
    "aqlyra-postgres",
    "aqlyra-redis",
    "aqlyra-backend",
    "aqlyra-frontend",
)


def find_ownership_conflicts(
    expected_project: str,
    existing_names: set[str],
    get_project_owner: Callable[[str], str],
) -> list[str]:
    if not expected_project.strip():
        return ["Compose project name is missing"]

    conflicts: list[str] = []
    for name in OWNED_NAMES:
        if name not in existing_names:
            continue
        owner = get_project_owner(name).strip()
        if owner != expected_project:
            # Print only container/project names, never environment values.
            conflicts.append(
                f"{name}: owned by {owner or 'unlabelled'}, "
                f"not {expected_project}"
            )
    return conflicts


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].strip():
        print("LOCAL_CONTAINER_OWNERSHIP=FAIL invalid project name")
        return 2

    try:
        response = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            check=True,
            capture_output=True,
            text=True,
        )
        names = set(response.stdout.splitlines())

        def get_owner(name: str) -> str:
            label = subprocess.run(
                [
                    "docker", "container", "inspect",
                    "--format",
                    '{{index .Config.Labels "com.docker.compose.project"}}',
                    name,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return label.stdout.strip()

        conflicts = find_ownership_conflicts(
            argv[1], names, get_owner
        )
    except (subprocess.CalledProcessError, OSError):
        print(
            "LOCAL_CONTAINER_OWNERSHIP=FAIL unable to inspect containers; "
            "Docker must be accessible"
        )
        return 2

    if conflicts:
        print("LOCAL_CONTAINER_OWNERSHIP=FAIL")
        for conflict in conflicts:
            print("FAIL: " + conflict)
        print(
            "Review 'docker ps -a' and Docker volume ownership. "
            "Do not delete or prune containers/volumes to bypass this check."
        )
        return 2

    print("LOCAL_CONTAINER_OWNERSHIP=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
