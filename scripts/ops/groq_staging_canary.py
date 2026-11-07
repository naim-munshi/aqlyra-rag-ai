#!/usr/bin/env python3
"""Strictly opt-in real Groq adapter smoke on GitHub's isolated runner.

Exactly three short, synthetic requests: one serial, then two concurrent.
This measures the provider adapter, NOT the app's RAG pipeline or production
Render throughput. The runner gets a dedicated low-quota *staging* key only.
Never use production credentials, private prompts or user files.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import os
from statistics import median
from time import perf_counter

MAX_REAL_CALLS = 3
MAX_OUTPUT_TOKENS = 128
MODEL = "openai/gpt-oss-20b"
SYSTEM = "This is an authorized synthetic test. Answer with one short sentence."
PROMPT = "Say that the synthetic staging canary is ready. No private data."

@dataclass(frozen=True)
class Sample:
    success: bool
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    failure_type: str | None


def check_staging_guards() -> str:
    if os.getenv("AQLYRA_REAL_GROQ_TEST_CONFIRMED") != "yes":
        raise ValueError("Real provider test requires explicit test-only consent")
    if os.getenv("APP_ENV") != "isolated_ci":
        raise ValueError("Only isolated CI may run this probe")
    if os.getenv("CI") != "true" or os.getenv("GITHUB_ACTIONS") != "true":
        raise ValueError("Real model canary must run in isolated GitHub Actions")
    if os.getenv("AQLYRA_TEST_MODEL", MODEL) != MODEL:
        raise ValueError("Model is restricted to a fixed bounded test model")
    if os.getenv("GROQ_API_KEY"):
        raise ValueError("Production-named GROQ_API_KEY must never be present")
    key = os.getenv("AQLYRA_STAGING_GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("Dedicated staging model key is not configured")
    return key


def call_one(key: str) -> Sample:
    from app.llms.groq_provider import GroqLLMProvider

    started = perf_counter()
    try:
        # A separate client per concurrent sample avoids shared-SDK races.
        model = GroqLLMProvider(
            api_key=key,
            model=MODEL,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            timeout_seconds=15,
            max_retries=0,
        )
        response = model.generate(instructions=SYSTEM, input_text=PROMPT)
        valid = (
            response.provider_name == "groq"
            and response.model_name == MODEL
            and bool(response.text.strip())
        )
        return Sample(
            success=valid,
            latency_ms=round((perf_counter() - started) * 1000, 1),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            failure_type=None if valid else "invalid_response",
        )
    except Exception as exc:
        # Never log Groq error messages: they can include the key or prompt.
        return Sample(
            success=False,
            latency_ms=round((perf_counter() - started) * 1000, 1),
            input_tokens=None,
            output_tokens=None,
            failure_type=type(exc).__name__,
        )


def summarize(count: int, samples: list[Sample]) -> dict:
    if count not in (1, 2) or len(samples) != count:
        raise ValueError("Unexpected real-provider request budget")
    durations = sorted(round(s.latency_ms, 1) for s in samples)
    return {
        "concurrent_calls": count,
        "requests": count,
        "successes": sum(s.success for s in samples),
        "failures": count - sum(s.success for s in samples),
        "p50_latency_ms": durations[(count - 1) // 2],
        "p95_latency_ms": durations[-1] if count <= 2 else None,
        "input_tokens_reported": sum(s.input_tokens or 0 for s in samples),
        "output_tokens_reported": sum(s.output_tokens or 0 for s in samples),
        "failure_types": sorted({s.failure_type for s in samples if s.failure_type}),
    }


def main() -> int:
    try:
        key = check_staging_guards()
    except ValueError as exc:
        print("REAL_GROQ_CANARY=NOT_RUN: " + str(exc), flush=True)
        return 2

    outcomes: list[dict] = []
    budget = 0
    for count in (1, 2):
        if budget + count > MAX_REAL_CALLS:
            raise RuntimeError("Internal real-model budget exceeded")
        budget += count
        if count == 1:
            samples = [call_one(key)]
        else:
            with ThreadPoolExecutor(max_workers=count) as pool:
                samples = [future.result() for future in as_completed(
                    [pool.submit(call_one, key) for _ in range(count)]
                )]
        summary = summarize(count, samples)
        outcomes.append(summary)
        print("REAL_GROQ_TIER=" + json.dumps(summary, sort_keys=True), flush=True)
        # Avoid repeat calls if authentication, provider rate limit, or
        # model availability fails on the first request.
        if summary["failures"]:
            break

    success = len(outcomes) == 2 and all(item["failures"] == 0 for item in outcomes)
    print("REAL_GROQ_CANARY=" + ("PASS" if success else "DEGRADED"),
          flush=True)
    print("REAL_GROQ_LIMITATIONS=3_SYNTHETIC_REQUESTS_NOT_RENDER_CAPACITY",
          flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
