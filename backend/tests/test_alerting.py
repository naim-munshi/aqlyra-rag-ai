from math import inf

from app.alerting.engine import (
    AlertStateTracker,
    AlertThresholds,
    MetricSnapshot,
    evaluate_metric_signals,
    interval_metrics,
    parse_prometheus_metrics,
)


def snapshot(
    *,
    start: float = 1.0,
    total: int = 0,
    errors: int = 0,
    buckets: dict[
        float,
        int,
    ] | None = None,
    unhandled: int = 0,
    rate_exceeded: int = 0,
    rate_backend: int = 0,
) -> MetricSnapshot:
    return MetricSnapshot(
        process_start_time=start,
        requests_total=total,
        requests_5xx=errors,
        latency_buckets=(
            buckets or {}
        ),
        unhandled_exceptions=unhandled,
        rate_limit_exceeded=rate_exceeded,
        rate_limit_backend_unavailable=(
            rate_backend
        ),
    )


def thresholds() -> AlertThresholds:
    return AlertThresholds(
        http_5xx_ratio=0.10,
        http_5xx_min_requests=20,
        p95_latency_seconds=3.0,
        latency_min_requests=20,
        rate_limit_exceeded=50,
        rate_limit_backend_unavailable=1,
        unhandled_exceptions=1,
    )


def test_parse_aqlyra_metrics() -> None:
    parsed = parse_prometheus_metrics(
        """
aqlyra_process_start_time_seconds 100
aqlyra_http_requests_total{method="GET",route="/",status="200"} 90
aqlyra_http_requests_total{method="GET",route="/",status="500"} 10
aqlyra_http_request_duration_seconds_bucket{method="GET",route="/",le="1"} 80
aqlyra_http_request_duration_seconds_bucket{method="GET",route="/",le="5"} 99
aqlyra_http_request_duration_seconds_bucket{method="GET",route="/",le="+Inf"} 100
aqlyra_http_unhandled_exceptions_total{method="GET",route="/"} 2
aqlyra_rate_limit_exceeded_total{bucket="rag-user"} 7
aqlyra_rate_limit_backend_unavailable_total{bucket="register-ip"} 1
""".strip()
    )

    assert parsed.requests_total == 100
    assert parsed.requests_5xx == 10
    assert parsed.latency_buckets[
        1.0
    ] == 80

    assert parsed.latency_buckets[
        inf
    ] == 100

    assert (
        parsed.unhandled_exceptions
        == 2
    )

    assert (
        parsed.rate_limit_exceeded
        == 7
    )

    assert (
        parsed
        .rate_limit_backend_unavailable
        == 1
    )


def test_interval_metrics_handle_counter_reset(
) -> None:
    previous = snapshot(
        start=1,
        total=100,
        errors=10,
        rate_exceeded=50,
    )

    current = snapshot(
        start=2,
        total=5,
        errors=1,
        rate_exceeded=3,
    )

    interval = interval_metrics(
        previous,
        current,
    )

    assert (
        interval.requests_total
        == 5
    )

    assert (
        interval.requests_5xx
        == 1
    )

    assert (
        interval.rate_limit_exceeded
        == 3
    )


def test_evaluator_detects_5xx_latency_and_operational_failures(
) -> None:
    previous = snapshot(
        total=100,
        errors=5,
        buckets={
            1.0: 90,
            5.0: 100,
            inf: 100,
        },
        unhandled=1,
        rate_exceeded=10,
        rate_backend=0,
    )

    current = snapshot(
        total=200,
        errors=25,
        buckets={
            1.0: 150,
            5.0: 198,
            inf: 200,
        },
        unhandled=2,
        rate_exceeded=70,
        rate_backend=1,
    )

    signals = (
        evaluate_metric_signals(
            previous,
            current,
            thresholds(),
        )
    )

    assert (
        signals[
            "http_5xx_rate"
        ][0]
        is True
    )

    assert (
        signals[
            "high_latency"
        ][0]
        is True
    )

    assert (
        signals[
            "unhandled_exceptions"
        ][0]
        is True
    )

    assert (
        signals[
            "rate_limit_spike"
        ][0]
        is True
    )

    assert (
        signals[
            "rate_limit_backend_unavailable"
        ][0]
        is True
    )


def test_low_volume_does_not_trigger_5xx_or_latency(
) -> None:
    previous = snapshot(
        total=0,
        buckets={
            5.0: 0,
            inf: 0,
        },
    )

    current = snapshot(
        total=2,
        errors=2,
        buckets={
            5.0: 2,
            inf: 2,
        },
    )

    signals = (
        evaluate_metric_signals(
            previous,
            current,
            thresholds(),
        )
    )

    assert not signals[
        "http_5xx_rate"
    ][0]

    assert not signals[
        "high_latency"
    ][0]


def test_alert_state_deduplicates_and_resolves(
) -> None:
    tracker = AlertStateTracker()

    assert (
        tracker.update(
            alert_name=(
                "service_unavailable"
            ),
            breached=True,
            details={},
            required_breaches=2,
            recovery_successes=2,
        )
        is None
    )

    firing = tracker.update(
        alert_name=(
            "service_unavailable"
        ),
        breached=True,
        details={
            "readiness":
                "unavailable",
        },
        required_breaches=2,
        recovery_successes=2,
    )

    assert firing is not None
    assert firing.status == "firing"

    assert (
        tracker.update(
            alert_name=(
                "service_unavailable"
            ),
            breached=True,
            details={},
            required_breaches=2,
            recovery_successes=2,
        )
        is None
    )

    assert (
        tracker.update(
            alert_name=(
                "service_unavailable"
            ),
            breached=False,
            details={},
            required_breaches=2,
            recovery_successes=2,
        )
        is None
    )

    resolved = tracker.update(
        alert_name=(
            "service_unavailable"
        ),
        breached=False,
        details={
            "readiness":
                "ready",
        },
        required_breaches=2,
        recovery_successes=2,
    )

    assert resolved is not None
    assert resolved.status == "resolved"


def test_alert_state_does_not_fire_on_single_transient_failure(
) -> None:
    tracker = AlertStateTracker()

    tracker.update(
        alert_name="metrics_unavailable",
        breached=True,
        details={},
        required_breaches=3,
    )

    result = tracker.update(
        alert_name="metrics_unavailable",
        breached=False,
        details={},
        required_breaches=3,
    )

    assert result is None
