#!/usr/bin/env python3
"""Bounded 10/25/50/100-user HTTP chat load in DISPOSABLE CI only.

Real HTTP -> FastAPI -> PostgreSQL -> chat persistence, deterministic LLM.
No Groq/Tavily, production accounts or external hosts. CI results CANNOT
establish Render Free, real Groq, voice, retrieval or live-user capacity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
from threading import Barrier, BrokenBarrierError, Lock
from time import perf_counter, monotonic, sleep
from urllib.parse import urlsplit

from ephemeral_fullstack_e2e import Client, SmokeFailure, create_account, expect, safe_url

TIERS = (10, 25, 50, 100)
MESSAGE = "Briefly greet a synthetic user in one sentence."
RESPONSE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Trial:
    status: int | None
    latency_ms: float
    valid: bool
    failure_type: str | None


class InFlight:
    def __init__(self):
        self.active = 0
        self.peak = 0
        self.lock = Lock()

    def start(self):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)

    def done(self):
        with self.lock:
            self.active -= 1


def nearest_rank(samples: list[float], quantile: float) -> float | None:
    if not samples:
        return None
    if not 0 < quantile <= 1:
        raise ValueError("Invalid quantile")
    ordered = sorted(samples)
    from math import ceil
    return round(ordered[ceil(quantile * len(ordered)) - 1], 1)


def assert_disposable_environment(origin: str) -> str:
    safe = safe_url(origin)  # fixed port 8000, only HTTP loopback, no redirects
    if os.getenv("AQLYRA_DISPOSABLE_LOAD_CONFIRMED") != "yes":
        raise ValueError("Explicit disposable CI confirmation is missing")
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise ValueError("Production environment is forbidden")
    if os.getenv("LLM_PROVIDER") != "deterministic":
        raise ValueError("Only deterministic LLM provider is allowed")
    if os.getenv("EMBEDDING_PROVIDER") != "deterministic":
        raise ValueError("Only deterministic embedding provider is allowed")
    if os.getenv("EMAIL_VERIFICATION_REQUIRED") != "false":
        raise ValueError("Synthetic account verification bypass is required")
    if os.getenv("RATE_LIMIT_ENABLED", "false") != "false":
        raise ValueError("Benchmark cannot exercise rate-limited public traffic")
    database = os.getenv("DATABASE_URL", "")
    try:
        parsed = urlsplit(database.replace("postgresql+psycopg://", "postgresql://", 1))
    except ValueError as exc:
        raise ValueError("Unexpected database connection configuration") from exc
    if parsed.scheme != "postgresql" or parsed.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("Database must be isolated local PostgreSQL, never Neon")
    if parsed.port not in (None, 5432) or parsed.username != "postgres":
        raise ValueError("Unexpected disposable PostgreSQL connection")
    if parsed.path != "/aqlyra_rag_ai":
        raise ValueError("Only dedicated disposable CI database may be benchmarked")
    return safe


def valid_chat_reply(status: int | None, payload: object) -> bool:
    if status != 200 or not isinstance(payload, dict):
        return False
    assistant = payload.get("assistant_message")
    user = payload.get("user_message")
    return (
        isinstance(assistant, dict)
        and assistant.get("role") == "assistant"
        and assistant.get("provider_name") == "deterministic"
        and isinstance(assistant.get("content"), str)
        and bool(assistant["content"].strip())
        and isinstance(user, dict)
        and user.get("content") == MESSAGE
        and user.get("role") == "user"
        and payload.get("mode") == "normal"
    )


def provision_accounts(origin: str, max_users: int) -> list[str]:
    api = Client(origin)
    accounts = []
    for index in range(max_users):
        token, _ = create_account(api, f"load{index:03d}")
        accounts.append(token)
    return accounts


def provision_conversations(origin: str, tokens: list[str]) -> list[str]:
    api = Client(origin)
    conversations = []
    for token in tokens:
        payload = expect(api.request(
            "POST", "/api/v1/conversations", token=token,
            data={"title": "Synthetic concurrency QA", "mode": "normal"},
        ), 201, "synthetic chat creation")
        conversation_id = payload.get("id")
        if not isinstance(conversation_id, str) or not conversation_id:
            raise SmokeFailure("No synthetic conversation ID")
        conversations.append(conversation_id)
    return conversations


def perform_tier(origin: str, tokens: list[str], conversation_ids: list[str]) -> dict:
    users = len(tokens)
    if users not in TIERS or len(conversation_ids) != users:
        raise ValueError("Only bounded, equal-sized synthetic cohorts are allowed")

    barrier = Barrier(users + 1, timeout=25)
    inflight = InFlight()

    def ask_one(index: int) -> Trial:
        try:
            barrier.wait()
        except BrokenBarrierError:
            return Trial(None, 0.0, False, "start_barrier")
        path = f"/api/v1/conversations/{conversation_ids[index]}/messages"
        inflight.start()
        started = perf_counter()
        try:
            response = Client(origin).request(
                "POST", path, token=tokens[index],
                data={"content": MESSAGE, "web_mode": "off"},
            )
            elapsed = (perf_counter() - started) * 1000
            ok = valid_chat_reply(response.status, response.payload)
            failure = None if ok else (
                "http_" + str(response.status)
                if response.status != 200 else "invalid_ai_response"
            )
            return Trial(response.status, round(elapsed, 1), ok, failure)
        except Exception as exc:
            elapsed = (perf_counter() - started) * 1000
            # Do not log URLs, credentials, headers or raw provider responses.
            return Trial(None, round(elapsed, 1), False, type(exc).__name__)
        finally:
            inflight.done()

    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = [executor.submit(ask_one, i) for i in range(users)]
        try:
            start = perf_counter()
            barrier.wait()
        except BrokenBarrierError as exc:
            raise SmokeFailure("Could not start simultaneous synthetic cohort") from exc
        results = [future.result() for future in as_completed(futures)]
        duration = max(perf_counter() - start, 0.001)

    durations = [trial.latency_ms for trial in results if trial.status is not None]
    succeeded = sum(trial.valid for trial in results)
    errors = Counter(
        trial.failure_type for trial in results if trial.failure_type
    )
    p95 = nearest_rank(durations, 0.95)
    return {
        "requested_concurrent_users": users,
        "peak_in_flight_http": inflight.peak,
        "requests": len(results),
        "successes": succeeded,
        "failures": users - succeeded,
        "success_rate_pct": round(succeeded * 100 / users, 2),
        "p50_latency_ms": nearest_rank(durations, 0.50),
        "p95_latency_ms": p95,
        "max_latency_ms": round(max(durations), 1) if durations else None,
        "wall_time_seconds": round(duration, 2),
        "successful_rps": round(succeeded / duration, 2),
        "failure_codes": dict(errors),
        "illustrative_ci_slo": (
            "pass" if succeeded / users >= 0.99
            and p95 is not None and p95 <= 10000 else "fail"
        ),
    }


def run(origin: str, *, pause_marker: Path | None = None, resume_marker: Path | None = None) -> dict:
    api = Client(origin)
    expect(api.request("GET", "/api/v1/health"), 200, "backend health")
    report = {
        "kind": "synthetic_disposable_chat_load",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "environment": "isolated_github_actions_ci",
        "database": "disposable_local_postgres",
        "providers": {"llm": "deterministic", "embedding": "deterministic",
                      "web_research": "off"},
        "backend_commit": os.getenv("GITHUB_SHA", "unrecorded"),
        "workload": "100 unique synthetic authenticated accounts, 1 short HTTP chat turn per user per tier; non-streaming",
        "ci_slo": "99% success and p95 <= 10s for this synthetic workload only",
        "tiers": [],
        "limitations": [
            "Not a production Render Free load test",
            "No real Groq latency, provider TPM/RPM, actual RAG or voice processing",
            "CI runner CPU, local Postgres and network differ from deployed infrastructure",
        ],
    }
    print("PROVISIONING=100 synthetic users on isolated loopback PostgreSQL", flush=True)
    accounts = provision_accounts(origin, max(TIERS))
    # Prepare ALL conversations before the optional resource-envelope cap is
    # applied. This isolates real chat-request latency from bcrypt/user setup.
    prepared = {
        count: provision_conversations(origin, accounts[:count])
        for count in TIERS
    }
    if pause_marker is not None:
        if resume_marker is None:
            raise ValueError("Both disposable synchronization markers are required")
        for marker in (pause_marker, resume_marker):
            if marker.parent != Path("/tmp") or marker.exists():
                raise ValueError("Markers must be new direct /tmp files")
        pause_marker.touch(mode=0o600)
        deadline = monotonic() + 120
        while not resume_marker.exists():
            if monotonic() >= deadline:
                raise SmokeFailure("Resource-envelope admission was not confirmed")
            sleep(0.2)
        print("DISPOSABLE_RESOURCE_ENVELOPE=ACKNOWLEDGED", flush=True)
    for count in TIERS:
        measured = perform_tier(origin, accounts[:count], prepared[count])
        report["tiers"].append(measured)
        print("LOAD_TIER=" + json.dumps(measured, sort_keys=True), flush=True)
    report["all_tiers_met_illustrative_ci_slo"] = all(
        t["illustrative_ci_slo"] == "pass" for t in report["tiers"]
    )
    report["maximum_tested_tier_meeting_ci_slo"] = max(
        (t["requested_concurrent_users"] for t in report["tiers"]
         if t["illustrative_ci_slo"] == "pass"), default=0,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--report-file", default="/tmp/aqlyra-synthetic-chat-load.json")
    parser.add_argument("--pause-marker", default=None,
                        help="CI only: signal when synthetic conversations are provisioned")
    parser.add_argument("--resume-marker", default=None,
                        help="CI only: resume measured tiers after Docker CPU cap is applied")
    args = parser.parse_args(argv)
    try:
        if bool(args.pause_marker) != bool(args.resume_marker):
            raise ValueError("Both CI synchronization markers must be supplied")
        origin = assert_disposable_environment(args.base_url)
        report = run(
            origin,
            pause_marker=Path(args.pause_marker) if args.pause_marker else None,
            resume_marker=Path(args.resume_marker) if args.resume_marker else None,
        )
        target = Path(args.report_file).resolve()
        if not str(target).startswith("/tmp/"):
            raise ValueError("Synthetic benchmark results must remain in /tmp")
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("CONCURRENCY_BENCHMARK=MEASURED", flush=True)
        print("CI_SLO_AT_ALL_TIERS=" +
              ("PASS" if report["all_tiers_met_illustrative_ci_slo"] else "NOT_MET"),
              flush=True)
        # A measured saturation is a valid benchmark result, not a harness failure.
        return 0
    except (ValueError, SmokeFailure, OSError, TimeoutError) as exc:
        print("CONCURRENCY_BENCHMARK=ABORTED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
