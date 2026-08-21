from datetime import (
    datetime,
    timezone,
)
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from uuid import uuid4

from app.alerting.engine import (
    AlertStateTracker,
    AlertThresholds,
    MetricSnapshot,
    evaluate_metric_signals,
    parse_prometheus_metrics,
)
from app.config.settings import settings
from app.core.logging import (
    app_logger,
    configure_logging,
)


_ALERT_METADATA = {
    "service_unavailable": (
        "critical",
        "Aqlyra readiness check is failing",
    ),
    "metrics_unavailable": (
        "warning",
        "Aqlyra metrics endpoint is unavailable",
    ),
    "http_5xx_rate": (
        "critical",
        "HTTP 5xx error rate exceeded threshold",
    ),
    "high_latency": (
        "warning",
        "HTTP p95 latency exceeded threshold",
    ),
    "unhandled_exceptions": (
        "critical",
        "Unhandled application exceptions detected",
    ),
    "rate_limit_backend_unavailable": (
        "critical",
        "Redis-backed rate limiting became unavailable",
    ),
    "rate_limit_spike": (
        "warning",
        "Abnormal rate-limit rejection volume detected",
    ),
}


def _touch_heartbeat() -> None:
    path = Path(
        settings.ALERT_HEARTBEAT_FILE
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        str(
            time.time()
        ),
        encoding="utf-8",
    )


def _fetch_text(
    url: str,
) -> tuple[
    bool,
    str,
]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent":
                "AqlyraAlertWorker/1.0",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=(
                settings
                .ALERT_HTTP_TIMEOUT_SECONDS
            ),
        ) as response:
            body = response.read().decode(
                "utf-8",
                errors="replace",
            )

            return (
                200
                <= response.status
                < 300,
                body,
            )

    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass

        return False, ""

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ):
        return False, ""


def _send_webhook(
    *,
    alert_name: str,
    status: str,
    details: dict[str, object],
) -> None:
    metadata = _ALERT_METADATA[
        alert_name
    ]

    severity = metadata[0]
    summary = metadata[1]

    payload = {
        "event_id": uuid4().hex,
        "observed_at": (
            datetime.now(
                timezone.utc
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        ),
        "service":
            settings.PROJECT_NAME,
        "environment":
            settings.APP_ENV,
        "alert_name":
            alert_name,
        "status":
            status,
        "severity":
            severity,
        "summary":
            summary,
        "details":
            details,
    }

    headers = {
        "Content-Type":
            "application/json",
        "User-Agent":
            "AqlyraAlertWorker/1.0",
    }

    token = (
        settings
        .ALERT_WEBHOOK_BEARER_TOKEN
        .strip()
    )

    if token:
        headers[
            "Authorization"
        ] = (
            "Bearer "
            + token
        )

    request = urllib.request.Request(
        settings.ALERT_WEBHOOK_URL,
        data=json.dumps(
            payload,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        ),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=(
            settings
            .ALERT_WEBHOOK_TIMEOUT_SECONDS
        ),
    ) as response:
        response.read()

        if not (
            200
            <= response.status
            < 300
        ):
            raise RuntimeError(
                "Alert webhook returned "
                "a non-success status"
            )


def _emit_transition(
    transition,
) -> None:
    severity = (
        _ALERT_METADATA[
            transition.alert_name
        ][0]
    )

    app_logger.warning(
        "alert_state_changed",
        alert_name=(
            transition.alert_name
        ),
        alert_status=(
            transition.status
        ),
        severity=severity,
        details=(
            transition.details
        ),
    )

    try:
        _send_webhook(
            alert_name=(
                transition.alert_name
            ),
            status=(
                transition.status
            ),
            details=(
                transition.details
            ),
        )

        app_logger.info(
            "alert_delivery_succeeded",
            alert_name=(
                transition.alert_name
            ),
            alert_status=(
                transition.status
            ),
        )

    except Exception:
        app_logger.exception(
            "alert_delivery_failed",
            alert_name=(
                transition.alert_name
            ),
            alert_status=(
                transition.status
            ),
        )


def _thresholds() -> AlertThresholds:
    return AlertThresholds(
        http_5xx_ratio=(
            settings
            .ALERT_HTTP_5XX_RATIO_THRESHOLD
        ),
        http_5xx_min_requests=(
            settings
            .ALERT_HTTP_5XX_MIN_REQUESTS
        ),
        p95_latency_seconds=(
            settings
            .ALERT_P95_LATENCY_SECONDS
        ),
        latency_min_requests=(
            settings
            .ALERT_LATENCY_MIN_REQUESTS
        ),
        rate_limit_exceeded=(
            settings
            .ALERT_RATE_LIMIT_EXCEEDED_THRESHOLD
        ),
        rate_limit_backend_unavailable=(
            settings
            .ALERT_RATE_LIMIT_BACKEND_UNAVAILABLE_THRESHOLD
        ),
        unhandled_exceptions=(
            settings
            .ALERT_UNHANDLED_EXCEPTION_THRESHOLD
        ),
    )


def _validate_configuration() -> None:
    positive_values = (
        settings.ALERT_POLL_INTERVAL_SECONDS,
        settings.ALERT_READINESS_FAILURES,
        settings.ALERT_RECOVERY_SUCCESSES,
        settings.ALERT_HTTP_TIMEOUT_SECONDS,
        settings.ALERT_WEBHOOK_TIMEOUT_SECONDS,
        settings.ALERT_HTTP_5XX_MIN_REQUESTS,
        settings.ALERT_LATENCY_MIN_REQUESTS,
        settings.ALERT_P95_LATENCY_SECONDS,
        settings.ALERT_RATE_LIMIT_EXCEEDED_THRESHOLD,
        settings.ALERT_RATE_LIMIT_BACKEND_UNAVAILABLE_THRESHOLD,
        settings.ALERT_UNHANDLED_EXCEPTION_THRESHOLD,
        settings.ALERT_HEARTBEAT_MAX_AGE_SECONDS,
    )

    if any(
        value <= 0
        for value in positive_values
    ):
        raise RuntimeError(
            "Alerting numeric configuration "
            "must be positive"
        )

    ratio = (
        settings
        .ALERT_HTTP_5XX_RATIO_THRESHOLD
    )

    if (
        ratio <= 0
        or ratio > 1
    ):
        raise RuntimeError(
            "ALERT_HTTP_5XX_RATIO_THRESHOLD "
            "must be between 0 and 1"
        )

    if (
        settings.ALERTING_ENABLED
        and not settings
        .ALERT_WEBHOOK_URL
        .strip()
    ):
        raise RuntimeError(
            "ALERT_WEBHOOK_URL is required "
            "when alerting is enabled"
        )


def run_worker() -> None:
    configure_logging()
    _validate_configuration()

    app_logger.info(
        "alert_worker_started",
        enabled=(
            settings.ALERTING_ENABLED
        ),
        poll_interval_seconds=(
            settings
            .ALERT_POLL_INTERVAL_SECONDS
        ),
    )

    tracker = AlertStateTracker()

    previous_snapshot: (
        MetricSnapshot
        | None
    ) = None

    if (
        settings
        .ALERT_STARTUP_GRACE_SECONDS
        > 0
    ):
        _touch_heartbeat()

        time.sleep(
            settings
            .ALERT_STARTUP_GRACE_SECONDS
        )

    base_url = (
        settings
        .ALERT_BACKEND_BASE_URL
        .rstrip("/")
    )

    readiness_url = (
        base_url
        + "/readiness"
    )

    metrics_url = (
        base_url
        + "/metrics"
    )

    while True:
        cycle_started = (
            time.monotonic()
        )

        try:
            _touch_heartbeat()

            if not settings.ALERTING_ENABLED:
                time.sleep(
                    min(
                        60,
                        settings
                        .ALERT_POLL_INTERVAL_SECONDS,
                    )
                )
                continue

            readiness_ok, _ = (
                _fetch_text(
                    readiness_url
                )
            )

            transition = (
                tracker.update(
                    alert_name=(
                        "service_unavailable"
                    ),
                    breached=(
                        not readiness_ok
                    ),
                    details={
                        "readiness":
                            (
                                "ready"
                                if readiness_ok
                                else "unavailable"
                            ),
                    },
                    required_breaches=(
                        settings
                        .ALERT_READINESS_FAILURES
                    ),
                    recovery_successes=(
                        settings
                        .ALERT_RECOVERY_SUCCESSES
                    ),
                )
            )

            if transition is not None:
                _emit_transition(
                    transition
                )

            metrics_ok, metrics_text = (
                _fetch_text(
                    metrics_url
                )
            )

            current_snapshot = None

            if metrics_ok:
                try:
                    current_snapshot = (
                        parse_prometheus_metrics(
                            metrics_text
                        )
                    )
                except Exception:
                    metrics_ok = False

            transition = (
                tracker.update(
                    alert_name=(
                        "metrics_unavailable"
                    ),
                    breached=(
                        not metrics_ok
                    ),
                    details={
                        "metrics":
                            (
                                "available"
                                if metrics_ok
                                else "unavailable"
                            ),
                    },
                    required_breaches=(
                        settings
                        .ALERT_READINESS_FAILURES
                    ),
                    recovery_successes=(
                        settings
                        .ALERT_RECOVERY_SUCCESSES
                    ),
                )
            )

            if transition is not None:
                _emit_transition(
                    transition
                )

            if (
                metrics_ok
                and current_snapshot
                is not None
            ):
                if (
                    previous_snapshot
                    is not None
                ):
                    signals = (
                        evaluate_metric_signals(
                            previous_snapshot,
                            current_snapshot,
                            _thresholds(),
                        )
                    )

                    for (
                        alert_name,
                        (
                            breached,
                            details,
                        ),
                    ) in signals.items():
                        transition = (
                            tracker.update(
                                alert_name=(
                                    alert_name
                                ),
                                breached=(
                                    breached
                                ),
                                details=(
                                    details
                                ),
                                required_breaches=1,
                                recovery_successes=(
                                    settings
                                    .ALERT_RECOVERY_SUCCESSES
                                ),
                            )
                        )

                        if (
                            transition
                            is not None
                        ):
                            _emit_transition(
                                transition
                            )

                previous_snapshot = (
                    current_snapshot
                )

        except Exception:
            app_logger.exception(
                "alert_worker_cycle_failed"
            )

        finally:
            _touch_heartbeat()

        elapsed = (
            time.monotonic()
            - cycle_started
        )

        sleep_seconds = max(
            0.1,
            (
                settings
                .ALERT_POLL_INTERVAL_SECONDS
                - elapsed
            ),
        )

        time.sleep(
            sleep_seconds
        )


if __name__ == "__main__":
    run_worker()
