#!/usr/bin/env python3
"""Offline fail-closed security/persistence checks for production Docker Compose.

Reads canonical Compose config JSON produced by Docker Compose.
"""
import json
import sys

REQUIRED = frozenset({
    "postgres", "redis", "backend", "frontend", "voice-worker",
    "alert-worker", "caddy",
})
APPS = frozenset({"backend", "frontend", "voice-worker", "alert-worker"})


def audit_services(services: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED - services.keys()
    for name in sorted(missing):
        errors.append(f"required service missing: {name}")

    for name in sorted(REQUIRED - missing):
        item = services[name]
        if item.get("privileged"):
            errors.append(f"{name}: privileged container forbidden")
        if item.get("network_mode") == "host":
            errors.append(f"{name}: host networking forbidden")

    for name, target in (("backend", 8000), ("postgres", 5432)):
        if name in missing:
            continue
        ports = services[name].get("ports", [])
        if len(ports) != 1:
            errors.append(f"{name}: expected exactly one localhost-only port")
            continue
        port = ports[0]
        if (
            port.get("host_ip") not in ("127.0.0.1", "::1")
            or port.get("protocol", "tcp") != "tcp"
            or int(port.get("target", -1)) != target
        ):
            errors.append(f"{name}: port {target} must bind loopback TCP")

    for name in ("redis", "frontend", "voice-worker", "alert-worker"):
        if name not in missing and services[name].get("ports"):
            errors.append(f"{name}: must not publish host ports")

    if "caddy" not in missing:
        ports = services["caddy"].get("ports", [])
        actual = {(int(p.get("target", -1)), p.get("protocol", "tcp")) for p in ports}
        expected = {(80, "tcp"), (443, "tcp"), (443, "udp")}
        if actual != expected or len(ports) != 3:
            errors.append("caddy: expose only TCP 80/443 and UDP 443")

    for name in sorted(APPS - missing):
        item = services[name]
        if "ALL" not in item.get("cap_drop", []):
            errors.append(f"{name}: must drop ALL Linux capabilities")
        if "no-new-privileges:true" not in item.get("security_opt", []):
            errors.append(f"{name}: no-new-privileges required")

    def named_volume(name: str, target: str) -> str | None:
        if name in missing:
            return None
        for mount in services[name].get("volumes", []):
            if (
                mount.get("target") == target
                and mount.get("type") == "volume"
                and mount.get("source")
            ):
                return mount["source"]
        errors.append(f"{name}: persistent named volume missing at {target}")
        return None

    backend_uploads = named_volume("backend", "/app/uploads")
    voice_uploads = named_volume("voice-worker", "/app/uploads")
    if backend_uploads and voice_uploads and backend_uploads != voice_uploads:
        errors.append("backend/voice-worker must share the uploads volume")
    named_volume("postgres", "/var/lib/postgresql/data")
    named_volume("caddy", "/data")
    named_volume("caddy", "/config")
    return errors


def main() -> int:
    try:
        document = json.load(sys.stdin)
        services = document["services"]
        if not isinstance(services, dict):
            raise ValueError("services must be an object")
    except (KeyError, ValueError, TypeError) as exc:
        print(f"DEPLOYMENT_CONTRACT=FAIL invalid Compose JSON: {exc}", file=sys.stderr)
        return 1

    findings = audit_services(services)
    for finding in findings:
        print("FAIL: " + finding, file=sys.stderr)
    if findings:
        print(f"DEPLOYMENT_CONTRACT=FAIL violations={len(findings)}")
        return 1
    print("DEPLOYMENT_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
