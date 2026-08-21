from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.monitoring import (
    record_rate_limit_backend_unavailable,
    record_rate_limit_exceeded,
    render_prometheus_metrics,
    reset_metrics_for_tests,
)
from app.middleware.observability import (
    setup_request_observability,
)


def build_test_app() -> FastAPI:
    app = FastAPI()

    setup_request_observability(
        app
    )

    @app.get(
        "/items/{item_id}"
    )
    async def item(
        item_id: str,
    ):
        return {
            "item_id": item_id,
        }

    @app.get("/explode")
    async def explode():
        raise RuntimeError(
            "synthetic monitoring failure"
        )

    @app.get(
        "/api/v1/readiness"
    )
    async def readiness():
        return {
            "status": "ready",
        }

    return app


def test_metrics_use_route_templates_not_dynamic_ids(
) -> None:
    reset_metrics_for_tests()

    app = build_test_app()

    client = TestClient(
        app
    )

    assert (
        client.get(
            "/items/alpha-user-value"
        ).status_code
        == 200
    )

    assert (
        client.get(
            "/items/beta-user-value"
        ).status_code
        == 200
    )

    metrics = (
        render_prometheus_metrics()
    )

    assert (
        'aqlyra_http_requests_total'
        '{method="GET",'
        'route="/items/{item_id}",'
        'status="200"} 2'
        in metrics
    )

    assert (
        "alpha-user-value"
        not in metrics
    )

    assert (
        "beta-user-value"
        not in metrics
    )


def test_metrics_record_latency_histogram(
) -> None:
    reset_metrics_for_tests()

    app = build_test_app()

    client = TestClient(
        app
    )

    response = client.get(
        "/items/example"
    )

    assert response.status_code == 200

    metrics = (
        render_prometheus_metrics()
    )

    assert (
        "aqlyra_http_request_duration_seconds_bucket"
        in metrics
    )

    assert (
        'route="/items/{item_id}"'
        in metrics
    )

    assert (
        "aqlyra_http_request_duration_seconds_sum"
        in metrics
    )

    assert (
        "aqlyra_http_request_duration_seconds_count"
        in metrics
    )


def test_unhandled_exception_has_metric(
) -> None:
    reset_metrics_for_tests()

    app = build_test_app()

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.get(
        "/explode"
    )

    assert response.status_code == 500

    metrics = (
        render_prometheus_metrics()
    )

    assert (
        'aqlyra_http_unhandled_exceptions_total'
        '{method="GET",route="/explode"} 1'
        in metrics
    )

    assert (
        'aqlyra_http_requests_total'
        '{method="GET",route="/explode",status="500"} 1'
        in metrics
    )


def test_health_monitoring_paths_do_not_pollute_http_metrics(
) -> None:
    reset_metrics_for_tests()

    app = build_test_app()

    client = TestClient(
        app
    )

    response = client.get(
        "/api/v1/readiness"
    )

    assert response.status_code == 200

    metrics = (
        render_prometheus_metrics()
    )

    assert (
        'route="/api/v1/readiness"'
        not in metrics
    )


def test_rate_limit_metrics_are_bounded_by_bucket_only(
) -> None:
    reset_metrics_for_tests()

    record_rate_limit_exceeded(
        "rag-user"
    )

    record_rate_limit_exceeded(
        "rag-user"
    )

    record_rate_limit_backend_unavailable(
        "register-ip"
    )

    metrics = (
        render_prometheus_metrics()
    )

    assert (
        'aqlyra_rate_limit_exceeded_total'
        '{bucket="rag-user"} 2'
        in metrics
    )

    assert (
        'aqlyra_rate_limit_backend_unavailable_total'
        '{bucket="register-ip"} 1'
        in metrics
    )


def test_unmatched_paths_share_one_bounded_label(
) -> None:
    reset_metrics_for_tests()

    app = build_test_app()

    client = TestClient(
        app
    )

    client.get(
        "/unknown/one"
    )

    client.get(
        "/unknown/two"
    )

    metrics = (
        render_prometheus_metrics()
    )

    assert (
        'route="__unmatched__"'
        in metrics
    )

    assert "/unknown/one" not in metrics
    assert "/unknown/two" not in metrics
