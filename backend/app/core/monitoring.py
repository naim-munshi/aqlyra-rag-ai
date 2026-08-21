from collections import Counter, defaultdict
from threading import Lock
from time import time
import re
from typing import Final

from fastapi import Request


_DURATION_BUCKETS: Final[
    tuple[float, ...]
] = (
    0.05,
    0.10,
    0.25,
    0.50,
    1.0,
    2.5,
    5.0,
    10.0,
)

_EXCLUDED_HTTP_PATHS: Final[
    frozenset[str]
] = frozenset(
    {
        "/api/v1/health",
        "/api/v1/readiness",
        "/api/v1/metrics",
    }
)

_LOCK = Lock()

_PROCESS_START_TIME = time()

_HTTP_REQUESTS: Counter[
    tuple[str, str, str]
] = Counter()

_HTTP_DURATION_BUCKETS: Counter[
    tuple[str, str, float]
] = Counter()

_HTTP_DURATION_SUM: dict[
    tuple[str, str],
    float,
] = defaultdict(float)

_HTTP_DURATION_COUNT: Counter[
    tuple[str, str]
] = Counter()

_HTTP_UNHANDLED_EXCEPTIONS: Counter[
    tuple[str, str]
] = Counter()

_RATE_LIMIT_EXCEEDED: Counter[
    str
] = Counter()

_RATE_LIMIT_BACKEND_UNAVAILABLE: Counter[
    str
] = Counter()


def _bounded_method(
    value: str,
) -> str:
    cleaned = (
        value.strip()
        .upper()
    )

    return (
        cleaned[:16]
        if cleaned
        else "UNKNOWN"
    )


def _bounded_route(
    value: str,
) -> str:
    cleaned = value.strip()

    if not cleaned:
        return "__unmatched__"

    if len(cleaned) > 240:
        return "__oversized_route__"

    return cleaned


def _bounded_bucket(
    value: str,
) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_.:-]",
        "_",
        value.strip(),
    )

    if not cleaned:
        return "unknown"

    return cleaned[:80]


def request_route_label(
    request: Request,
) -> str:
    route = request.scope.get(
        "route"
    )

    route_path = getattr(
        route,
        "path",
        None,
    )

    if (
        isinstance(
            route_path,
            str,
        )
        and route_path
    ):
        return _bounded_route(
            route_path
        )

    return "__unmatched__"


def should_record_http_metrics(
    raw_path: str,
) -> bool:
    return (
        raw_path
        not in _EXCLUDED_HTTP_PATHS
    )


def record_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    method_label = (
        _bounded_method(
            method
        )
    )

    route_label = (
        _bounded_route(
            route
        )
    )

    status_label = str(
        int(
            status_code
        )
    )

    duration = max(
        0.0,
        float(
            duration_seconds
        ),
    )

    duration_key = (
        method_label,
        route_label,
    )

    with _LOCK:
        _HTTP_REQUESTS[
            (
                method_label,
                route_label,
                status_label,
            )
        ] += 1

        _HTTP_DURATION_COUNT[
            duration_key
        ] += 1

        _HTTP_DURATION_SUM[
            duration_key
        ] += duration

        for bucket in (
            _DURATION_BUCKETS
        ):
            if duration <= bucket:
                _HTTP_DURATION_BUCKETS[
                    (
                        method_label,
                        route_label,
                        bucket,
                    )
                ] += 1


def record_unhandled_exception(
    *,
    method: str,
    route: str,
) -> None:
    key = (
        _bounded_method(
            method
        ),
        _bounded_route(
            route
        ),
    )

    with _LOCK:
        _HTTP_UNHANDLED_EXCEPTIONS[
            key
        ] += 1


def record_rate_limit_exceeded(
    bucket: str,
) -> None:
    label = _bounded_bucket(
        bucket
    )

    with _LOCK:
        _RATE_LIMIT_EXCEEDED[
            label
        ] += 1


def record_rate_limit_backend_unavailable(
    bucket: str,
) -> None:
    label = _bounded_bucket(
        bucket
    )

    with _LOCK:
        _RATE_LIMIT_BACKEND_UNAVAILABLE[
            label
        ] += 1


def _escape_label(
    value: str,
) -> str:
    return (
        value
        .replace(
            "\\",
            "\\\\",
        )
        .replace(
            "\n",
            "\\n",
        )
        .replace(
            '"',
            '\\"',
        )
    )


def _labels(
    **values: str,
) -> str:
    rendered = ",".join(
        (
            f'{key}="'
            f'{_escape_label(value)}'
            f'"'
        )
        for key, value
        in values.items()
    )

    return (
        "{"
        + rendered
        + "}"
    )


def render_prometheus_metrics(
) -> str:
    with _LOCK:
        requests = dict(
            _HTTP_REQUESTS
        )

        duration_buckets = dict(
            _HTTP_DURATION_BUCKETS
        )

        duration_sum = dict(
            _HTTP_DURATION_SUM
        )

        duration_count = dict(
            _HTTP_DURATION_COUNT
        )

        exceptions = dict(
            _HTTP_UNHANDLED_EXCEPTIONS
        )

        rate_exceeded = dict(
            _RATE_LIMIT_EXCEEDED
        )

        rate_unavailable = dict(
            _RATE_LIMIT_BACKEND_UNAVAILABLE
        )

    lines: list[str] = [
        (
            "# HELP "
            "aqlyra_process_start_time_seconds "
            "Unix timestamp when this backend process started."
        ),
        (
            "# TYPE "
            "aqlyra_process_start_time_seconds gauge"
        ),
        (
            "aqlyra_process_start_time_seconds "
            f"{_PROCESS_START_TIME:.6f}"
        ),
        (
            "# HELP "
            "aqlyra_http_requests_total "
            "Completed application HTTP requests."
        ),
        (
            "# TYPE "
            "aqlyra_http_requests_total counter"
        ),
    ]

    for (
        method,
        route,
        status_code,
    ), count in sorted(
        requests.items()
    ):
        lines.append(
            (
                "aqlyra_http_requests_total"
                + _labels(
                    method=method,
                    route=route,
                    status=status_code,
                )
                + f" {count}"
            )
        )

    lines.extend(
        [
            (
                "# HELP "
                "aqlyra_http_request_duration_seconds "
                "Application HTTP request duration."
            ),
            (
                "# TYPE "
                "aqlyra_http_request_duration_seconds histogram"
            ),
        ]
    )

    for (
        method,
        route,
    ), count in sorted(
        duration_count.items()
    ):
        for bucket in (
            _DURATION_BUCKETS
        ):
            bucket_count = (
                duration_buckets.get(
                    (
                        method,
                        route,
                        bucket,
                    ),
                    0,
                )
            )

            lines.append(
                (
                    "aqlyra_http_request_duration_seconds_bucket"
                    + _labels(
                        method=method,
                        route=route,
                        le=f"{bucket:g}",
                    )
                    + f" {bucket_count}"
                )
            )

        lines.append(
            (
                "aqlyra_http_request_duration_seconds_bucket"
                + _labels(
                    method=method,
                    route=route,
                    le="+Inf",
                )
                + f" {count}"
            )
        )

        lines.append(
            (
                "aqlyra_http_request_duration_seconds_sum"
                + _labels(
                    method=method,
                    route=route,
                )
                + " "
                + (
                    f"{duration_sum.get((method, route), 0.0):.9f}"
                )
            )
        )

        lines.append(
            (
                "aqlyra_http_request_duration_seconds_count"
                + _labels(
                    method=method,
                    route=route,
                )
                + f" {count}"
            )
        )

    lines.extend(
        [
            (
                "# HELP "
                "aqlyra_http_unhandled_exceptions_total "
                "Unhandled application exceptions."
            ),
            (
                "# TYPE "
                "aqlyra_http_unhandled_exceptions_total counter"
            ),
        ]
    )

    for (
        method,
        route,
    ), count in sorted(
        exceptions.items()
    ):
        lines.append(
            (
                "aqlyra_http_unhandled_exceptions_total"
                + _labels(
                    method=method,
                    route=route,
                )
                + f" {count}"
            )
        )

    lines.extend(
        [
            (
                "# HELP "
                "aqlyra_rate_limit_exceeded_total "
                "Requests rejected by an Aqlyra rate-limit bucket."
            ),
            (
                "# TYPE "
                "aqlyra_rate_limit_exceeded_total counter"
            ),
        ]
    )

    for bucket, count in sorted(
        rate_exceeded.items()
    ):
        lines.append(
            (
                "aqlyra_rate_limit_exceeded_total"
                + _labels(
                    bucket=bucket
                )
                + f" {count}"
            )
        )

    lines.extend(
        [
            (
                "# HELP "
                "aqlyra_rate_limit_backend_unavailable_total "
                "Rate-limit operations that failed because Redis was unavailable."
            ),
            (
                "# TYPE "
                "aqlyra_rate_limit_backend_unavailable_total counter"
            ),
        ]
    )

    for bucket, count in sorted(
        rate_unavailable.items()
    ):
        lines.append(
            (
                "aqlyra_rate_limit_backend_unavailable_total"
                + _labels(
                    bucket=bucket
                )
                + f" {count}"
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    )


def reset_metrics_for_tests(
) -> None:
    with _LOCK:
        _HTTP_REQUESTS.clear()
        _HTTP_DURATION_BUCKETS.clear()
        _HTTP_DURATION_SUM.clear()
        _HTTP_DURATION_COUNT.clear()
        _HTTP_UNHANDLED_EXCEPTIONS.clear()
        _RATE_LIMIT_EXCEEDED.clear()
        _RATE_LIMIT_BACKEND_UNAVAILABLE.clear()
