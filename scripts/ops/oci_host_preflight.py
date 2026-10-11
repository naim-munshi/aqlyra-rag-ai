#!/usr/bin/env python3
"""Non-destructive host checks before Oracle Always Free staging deployment."""

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = Path(sys.argv[1] if len(sys.argv) > 1 else "backend/.env.production")
if not ENV_FILE.is_absolute():
    ENV_FILE = ROOT / ENV_FILE

errors = []


def check(condition: bool, message: str) -> None:
    print(("PASS" if condition else "FAIL") + ": " + message)
    if not condition:
        errors.append(message)


def command(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


check(platform.system() == "Linux", "Ubuntu/Linux host detected")
check(platform.machine() in {"aarch64", "arm64"}, "ARM64 Ampere host")
check((os.cpu_count() or 0) >= 2, "At least 2 CPUs")
if Path("/proc/meminfo").exists():
    meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
    ram_kib = int(next(
        line.split()[1] for line in meminfo.splitlines()
        if line.startswith("MemTotal:")
    ))
    check(ram_kib >= 8 * 1024 * 1024, "At least 8 GiB of RAM")
else:
    check(False, "Linux memory information available")

check(
    shutil.disk_usage(ROOT).free >= 15 * 1024**3,
    "At least 15 GiB free for Docker builds and persistent state",
)
for tool in ("docker", "git", "curl", "python3"):
    check(shutil.which(tool) is not None, tool + " installed")

check(ENV_FILE.is_file(), "Private production environment file exists")
if ENV_FILE.is_file():
    check(
        ENV_FILE.stat().st_mode & 0o077 == 0,
        "Environment file denies group and other access",
    )

if shutil.which("docker"):
    info = command(["docker", "info"])
    check(info is not None and info.returncode == 0, "Docker daemon reachable")
    compose = command(["docker", "compose", "version"])
    check(compose is not None and compose.returncode == 0, "Docker Compose v2")

if ENV_FILE.is_file():
    preflight = command([
        "bash", "scripts/ops/production-preflight.sh", str(ENV_FILE)
    ])
    check(
        preflight is not None and preflight.returncode == 0,
        "Application production preflight (configure required secrets)",
    )

    if shutil.which("docker"):
        result = command([
            "docker", "compose", "--env-file", str(ENV_FILE),
            "--profile", "production", "config", "--format", "json",
        ])
        check(
            result is not None and result.returncode == 0,
            "Production Compose configuration",
        )
        if result is not None and result.returncode == 0:
            try:
                services = json.loads(result.stdout)["services"]
                issues = []
                for name, target in (("backend", 8000), ("postgres", 5432)):
                    ports = services.get(name, {}).get("ports", [])
                    if len(ports) != 1 or int(ports[0]["target"]) != target:
                        issues.append(name + " has unexpected port bindings")
                    elif ports[0].get("host_ip") not in ("127.0.0.1", "::1"):
                        issues.append(name + " is publicly exposed")

                for name in ("redis", "frontend", "voice-worker", "alert-worker"):
                    if services.get(name, {}).get("ports"):
                        issues.append(name + " is publicly exposed")

                caddy = services.get("caddy", {}).get("ports", [])
                if {int(item["target"]) for item in caddy} != {80, 443}:
                    issues.append("Caddy should expose only HTTP(S)")

                for issue in issues:
                    print("FAIL: " + issue)
                    errors.append(issue)
                check(not issues, "Only Caddy accepts publicly routed ports")
            except (ValueError, KeyError, TypeError):
                check(False, "Could not inspect Compose published ports")

print("OCI_HOST_PREFLIGHT=" + ("FAIL" if errors else "PASS"))
print("OCI billing eligibility, live SSL, and ARM wheel support require separate checks.")
raise SystemExit(1 if errors else 0)
