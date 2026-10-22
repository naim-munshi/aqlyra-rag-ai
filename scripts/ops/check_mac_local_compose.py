#!/usr/bin/env python3
"""Fail closed if the developer-only Compose override exposes local services."""
import json
import sys


def audit_local(services: dict) -> list[str]:
    problems: list[str] = []

    def port_only_loopback(name: str, target: int) -> None:
        item = services.get(name)
        if not isinstance(item, dict):
            problems.append(f"{name}: required service missing")
            return
        ports = item.get("ports", [])
        if len(ports) != 1:
            problems.append(f"{name}: exactly one loopback port required")
            return
        port = ports[0]
        if (
            port.get("host_ip") not in {"127.0.0.1", "::1"}
            or port.get("protocol", "tcp") != "tcp"
            or int(port.get("target", -1)) != target
        ):
            problems.append(f"{name}: port {target} must bind loopback TCP")

    for name, port in (
        ("frontend", 3000),
        ("backend", 8000),
        ("postgres", 5432),
        ("mailpit", 8025),
    ):
        port_only_loopback(name, port)

    redis = services.get("redis")
    if redis is None or redis.get("ports"):
        problems.append("redis: required without any host-published port")

    mailpit = services.get("mailpit", {})
    if len(mailpit.get("ports", [])) != 1:
        problems.append("mailpit: SMTP port 1025 must never be host-published")

    backend = services.get("backend", {})
    env = backend.get("environment", {})
    requirements = {
        "APP_ENV": "development",
        "SMTP_HOST": "mailpit",
        "SMTP_PORT": "1025",
        "SMTP_USE_SSL": "false",
        "SMTP_STARTTLS": "false",
        "EMAIL_VERIFICATION_REQUIRED": "true",
    }
    for key, expected in requirements.items():
        value = str(env.get(key, "")).lower()
        if value != expected:
            problems.append(f"backend: {key} must equal {expected!r}")

    if not backend.get("depends_on", {}).get("mailpit"):
        problems.append("backend: must depend on local SMTP capture service")

    return problems


def main() -> int:
    try:
        doc = json.load(sys.stdin)
        services = doc["services"]
        if not isinstance(services, dict):
            raise ValueError("services must be an object")
    except (TypeError, ValueError, KeyError) as exc:
        print(f"MAC_LOCAL_CONTRACT=FAIL: invalid configuration: {exc}", file=sys.stderr)
        return 1

    problems = audit_local(services)
    for problem in problems:
        print("FAIL: " + problem, file=sys.stderr)

    if problems:
        print(f"MAC_LOCAL_CONTRACT=FAIL violations={len(problems)}")
        return 1
    print("MAC_LOCAL_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
