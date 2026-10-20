#!/usr/bin/env python3
"""Bounded read-only staging probe; not a benchmark of LLM/RAG inference.

Use only with owned or explicitly authorized endpoints.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import math
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from staging_smoke import NoRedirect, validate_base_url


@dataclass(frozen=True)
class Observation:
    milliseconds: float
    status: int | None
    valid: bool


def percentile_nearest_rank(values: list[float], fraction: float) -> float:
    if not values or not 0 < fraction <= 1:
        raise ValueError("observations and percentile in (0,1] required")
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * fraction) - 1]


def measure(url: str, timeout: float) -> Observation:
    req = Request(
        url, method="GET",
        headers={
            "User-Agent": "Aqlyra-Staging-Probe/1.0",
            "Cache-Control": "no-store",
        },
    )
    start = perf_counter()
    opener = build_opener(NoRedirect())
    try:
        try:
            response = opener.open(req, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read(65537)
            status = response.status
            cache_control = response.headers.get("Cache-Control", "").lower()
            valid = (
                status == 200
                and len(body) <= 65536
                and (
                    not url.endswith("/api/health")
                    or "no-store" in cache_control
                )
            )
    except (URLError, OSError, TimeoutError):
        return Observation((perf_counter() - start) * 1000, None, False)

    return Observation((perf_counter() - start) * 1000, status, valid)


def probe(url: str, count: int, concurrency: int, timeout: float):
    start = perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(measure, url, timeout) for _ in range(count)]
        samples = [future.result() for future in as_completed(futures)]
    return samples, perf_counter() - start


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--allow-http-loopback", action="store_true",
        help="Only for local testing; live deployments require HTTPS",
    )
    parser.add_argument("--path", choices=("/api/health", "/login"),
                        default="/api/health")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--max-p95-ms", type=float,
        help="Optional p95 latency regression gate in milliseconds",
    )
    args = parser.parse_args(argv)

    if not 1 <= args.requests <= 100:
        parser.error("--requests must be between 1 and 100")
    if not 1 <= args.concurrency <= 4:
        parser.error("--concurrency must be between 1 and 4")
    if not 0 < args.timeout <= 15:
        parser.error("--timeout must be between 0 and 15 seconds")
    if args.max_p95_ms is not None and args.max_p95_ms <= 0:
        parser.error("--max-p95-ms must be positive")

    try:
        origin = validate_base_url(
            args.base_url, args.allow_http_loopback
        )
    except ValueError as exc:
        parser.error(str(exc))

    samples, elapsed = probe(
        origin + args.path, args.requests, args.concurrency, args.timeout
    )
    p50 = percentile_nearest_rank([s.milliseconds for s in samples], 0.50)
    p95 = percentile_nearest_rank([s.milliseconds for s in samples], 0.95)
    failures = sum(not s.valid for s in samples)
    print(f"PATH={args.path}")
    print(f"REQUESTS={len(samples)} CONCURRENCY={args.concurrency} ERRORS={failures}")
    print(f"LATENCY_P50_MS={p50:.1f} LATENCY_P95_MS={p95:.1f}")
    print(f"THROUGHPUT_RPS={len(samples) / max(elapsed, 0.000001):.2f}")

    if failures:
        print("PERFORMANCE_PROBE=FAIL transport/status/cache response")
        return 1
    if args.max_p95_ms is not None and p95 > args.max_p95_ms:
        print("PERFORMANCE_PROBE=FAIL p95 target exceeded")
        return 1

    print("PERFORMANCE_PROBE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
