from dataclasses import dataclass
from math import ceil, inf
import re


_METRIC_RE = re.compile(
    r"^([A-Za-z_:][A-Za-z0-9_:]*)"
    r"(?:\{(.*)\})?\s+"
    r"([-+A-Za-z0-9.eE]+)$"
)

_LABEL_RE = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)='
    r'"((?:\\.|[^"])*)"'
)


@dataclass(frozen=True)
class MetricSnapshot:
    process_start_time: float | None
    requests_total: int
    requests_5xx: int
    latency_buckets: dict[float, int]
    unhandled_exceptions: int
    rate_limit_exceeded: int
    rate_limit_backend_unavailable: int


@dataclass(frozen=True)
class IntervalMetrics:
    requests_total: int
    requests_5xx: int
    http_5xx_ratio: float
    p95_upper_bound_seconds: float | None
    unhandled_exceptions: int
    rate_limit_exceeded: int
    rate_limit_backend_unavailable: int


@dataclass(frozen=True)
class AlertThresholds:
    http_5xx_ratio: float
    http_5xx_min_requests: int
    p95_latency_seconds: float
    latency_min_requests: int
    rate_limit_exceeded: int
    rate_limit_backend_unavailable: int
    unhandled_exceptions: int


@dataclass(frozen=True)
class AlertTransition:
    alert_name: str
    status: str
    details: dict[str, object]


@dataclass
class _AlertState:
    active: bool = False
    breach_count: int = 0
    healthy_count: int = 0


class AlertStateTracker:
    def __init__(
        self,
    ) -> None:
        self._states: dict[
            str,
            _AlertState,
        ] = {}

    def update(
        self,
        *,
        alert_name: str,
        breached: bool,
        details: dict[str, object],
        required_breaches: int = 1,
        recovery_successes: int = 2,
    ) -> AlertTransition | None:
        required_breaches = max(
            1,
            int(required_breaches),
        )

        recovery_successes = max(
            1,
            int(recovery_successes),
        )

        state = self._states.setdefault(
            alert_name,
            _AlertState(),
        )

        if breached:
            state.healthy_count = 0

            if state.active:
                return None

            state.breach_count += 1

            if (
                state.breach_count
                < required_breaches
            ):
                return None

            state.active = True
            state.breach_count = 0

            return AlertTransition(
                alert_name=alert_name,
                status="firing",
                details=details,
            )

        state.breach_count = 0

        if not state.active:
            state.healthy_count = 0
            return None

        state.healthy_count += 1

        if (
            state.healthy_count
            < recovery_successes
        ):
            return None

        state.active = False
        state.healthy_count = 0

        return AlertTransition(
            alert_name=alert_name,
            status="resolved",
            details=details,
        )


def _parse_labels(
    raw: str | None,
) -> dict[str, str]:
    if not raw:
        return {}

    values: dict[str, str] = {}

    for match in _LABEL_RE.finditer(
        raw
    ):
        value = (
            match.group(2)
            .replace(
                r"\\",
                "\\",
            )
            .replace(
                r"\"",
                '"',
            )
            .replace(
                r"\n",
                "\n",
            )
        )

        values[
            match.group(1)
        ] = value

    return values


def _metric_number(
    raw: str,
) -> float:
    if raw == "+Inf":
        return inf

    if raw == "-Inf":
        return -inf

    return float(raw)


def parse_prometheus_metrics(
    text: str,
) -> MetricSnapshot:
    process_start: float | None = None

    requests_total = 0
    requests_5xx = 0

    latency_buckets: dict[
        float,
        int,
    ] = {}

    unhandled = 0
    rate_exceeded = 0
    rate_backend_unavailable = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
        ):
            continue

        match = _METRIC_RE.fullmatch(
            line
        )

        if match is None:
            continue

        name = match.group(1)
        labels = _parse_labels(
            match.group(2)
        )

        try:
            value = _metric_number(
                match.group(3)
            )
        except ValueError:
            continue

        if (
            name
            == "aqlyra_process_start_time_seconds"
        ):
            process_start = value
            continue

        if (
            name
            == "aqlyra_http_requests_total"
        ):
            count = int(value)
            requests_total += count

            status = labels.get(
                "status",
                "",
            )

            if status.startswith("5"):
                requests_5xx += count

            continue

        if (
            name
            == "aqlyra_http_request_duration_seconds_bucket"
        ):
            le = labels.get(
                "le"
            )

            if le is None:
                continue

            try:
                bucket = _metric_number(
                    le
                )
            except ValueError:
                continue

            latency_buckets[
                bucket
            ] = (
                latency_buckets.get(
                    bucket,
                    0,
                )
                + int(value)
            )

            continue

        if (
            name
            == "aqlyra_http_unhandled_exceptions_total"
        ):
            unhandled += int(value)
            continue

        if (
            name
            == "aqlyra_rate_limit_exceeded_total"
        ):
            rate_exceeded += int(value)
            continue

        if (
            name
            == "aqlyra_rate_limit_backend_unavailable_total"
        ):
            rate_backend_unavailable += int(
                value
            )

    return MetricSnapshot(
        process_start_time=(
            process_start
        ),
        requests_total=(
            requests_total
        ),
        requests_5xx=(
            requests_5xx
        ),
        latency_buckets=(
            latency_buckets
        ),
        unhandled_exceptions=(
            unhandled
        ),
        rate_limit_exceeded=(
            rate_exceeded
        ),
        rate_limit_backend_unavailable=(
            rate_backend_unavailable
        ),
    )


def _counter_delta(
    previous: int,
    current: int,
    *,
    reset: bool,
) -> int:
    if reset or current < previous:
        return max(
            0,
            current,
        )

    return max(
        0,
        current - previous,
    )


def interval_metrics(
    previous: MetricSnapshot,
    current: MetricSnapshot,
) -> IntervalMetrics:
    reset = (
        previous.process_start_time
        is not None
        and current.process_start_time
        is not None
        and previous.process_start_time
        != current.process_start_time
    )

    requests_total = _counter_delta(
        previous.requests_total,
        current.requests_total,
        reset=reset,
    )

    requests_5xx = _counter_delta(
        previous.requests_5xx,
        current.requests_5xx,
        reset=reset,
    )

    bucket_delta: dict[
        float,
        int,
    ] = {}

    all_buckets = (
        set(
            previous.latency_buckets
        )
        | set(
            current.latency_buckets
        )
    )

    for bucket in all_buckets:
        bucket_delta[
            bucket
        ] = _counter_delta(
            previous.latency_buckets.get(
                bucket,
                0,
            ),
            current.latency_buckets.get(
                bucket,
                0,
            ),
            reset=reset,
        )

    p95: float | None = None

    histogram_count = (
        bucket_delta.get(
            inf,
            0,
        )
    )

    if histogram_count > 0:
        target = ceil(
            histogram_count
            * 0.95
        )

        for bucket in sorted(
            value
            for value
            in bucket_delta
            if value != inf
        ):
            if (
                bucket_delta[
                    bucket
                ]
                >= target
            ):
                p95 = bucket
                break

        if p95 is None:
            p95 = inf

    ratio = (
        requests_5xx
        / requests_total
        if requests_total > 0
        else 0.0
    )

    return IntervalMetrics(
        requests_total=(
            requests_total
        ),
        requests_5xx=(
            requests_5xx
        ),
        http_5xx_ratio=ratio,
        p95_upper_bound_seconds=p95,
        unhandled_exceptions=(
            _counter_delta(
                previous.unhandled_exceptions,
                current.unhandled_exceptions,
                reset=reset,
            )
        ),
        rate_limit_exceeded=(
            _counter_delta(
                previous.rate_limit_exceeded,
                current.rate_limit_exceeded,
                reset=reset,
            )
        ),
        rate_limit_backend_unavailable=(
            _counter_delta(
                previous
                .rate_limit_backend_unavailable,
                current
                .rate_limit_backend_unavailable,
                reset=reset,
            )
        ),
    )


def evaluate_metric_signals(
    previous: MetricSnapshot,
    current: MetricSnapshot,
    thresholds: AlertThresholds,
) -> dict[
    str,
    tuple[
        bool,
        dict[str, object],
    ],
]:
    interval = interval_metrics(
        previous,
        current,
    )

    enough_5xx_traffic = (
        interval.requests_total
        >= thresholds.http_5xx_min_requests
    )

    high_5xx = (
        enough_5xx_traffic
        and interval.http_5xx_ratio
        >= thresholds.http_5xx_ratio
    )

    enough_latency_traffic = (
        interval.requests_total
        >= thresholds.latency_min_requests
    )

    p95 = (
        interval
        .p95_upper_bound_seconds
    )

    high_latency = (
        enough_latency_traffic
        and p95 is not None
        and p95
        >= thresholds.p95_latency_seconds
    )

    return {
        "http_5xx_rate": (
            high_5xx,
            {
                "requests":
                    interval.requests_total,
                "http_5xx":
                    interval.requests_5xx,
                "ratio":
                    round(
                        interval.http_5xx_ratio,
                        4,
                    ),
                "threshold":
                    thresholds.http_5xx_ratio,
            },
        ),
        "high_latency": (
            high_latency,
            {
                "requests":
                    interval.requests_total,
                "p95_upper_bound_seconds":
                    (
                        "inf"
                        if p95 == inf
                        else p95
                    ),
                "threshold_seconds":
                    thresholds
                    .p95_latency_seconds,
            },
        ),
        "unhandled_exceptions": (
            (
                interval.unhandled_exceptions
                >= thresholds
                .unhandled_exceptions
            ),
            {
                "count":
                    interval.unhandled_exceptions,
                "threshold":
                    thresholds
                    .unhandled_exceptions,
            },
        ),
        "rate_limit_backend_unavailable": (
            (
                interval
                .rate_limit_backend_unavailable
                >= thresholds
                .rate_limit_backend_unavailable
            ),
            {
                "count":
                    interval
                    .rate_limit_backend_unavailable,
                "threshold":
                    thresholds
                    .rate_limit_backend_unavailable,
            },
        ),
        "rate_limit_spike": (
            (
                interval.rate_limit_exceeded
                >= thresholds
                .rate_limit_exceeded
            ),
            {
                "count":
                    interval.rate_limit_exceeded,
                "threshold":
                    thresholds
                    .rate_limit_exceeded,
            },
        ),
    }
