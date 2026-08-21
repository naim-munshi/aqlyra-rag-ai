import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import (
    app_logger,
    reset_request_id,
    set_request_id,
)
from app.core.monitoring import (
    record_http_request,
    record_unhandled_exception,
    request_route_label,
    should_record_http_metrics,
)


_REQUEST_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9._-]{8,128}$"
)


_QUIET_SUCCESS_PATHS = {
    "/api/v1/health",
    "/api/v1/readiness",
    "/api/v1/metrics",
}


def _resolve_request_id(
    request: Request,
) -> str:
    supplied = (
        request.headers.get(
            "X-Request-ID",
            "",
        )
        .strip()
    )

    if (
        supplied
        and _REQUEST_ID_PATTERN
        .fullmatch(
            supplied
        )
    ):
        return supplied

    return uuid4().hex


def setup_request_observability(
    app: FastAPI,
) -> None:
    @app.middleware("http")
    async def request_observability(
        request: Request,
        call_next,
    ):
        request_id = (
            _resolve_request_id(
                request
            )
        )

        context_token = (
            set_request_id(
                request_id
            )
        )

        started_at = (
            perf_counter()
        )

        path = request.url.path
        method = request.method

        try:
            try:
                response = (
                    await call_next(
                        request
                    )
                )

            except Exception:
                duration_ms = round(
                    (
                        perf_counter()
                        - started_at
                    )
                    * 1_000,
                    2,
                )

                route = request_route_label(
                    request
                )

                record_unhandled_exception(
                    method=method,
                    route=route,
                )

                app_logger.exception(
                    "http_request_unhandled_exception",
                    method=method,
                    path=route,
                    duration_ms=(
                        duration_ms
                    ),
                )

                response = JSONResponse(
                    status_code=500,
                    content={
                        "detail": (
                            "Internal server error"
                        ),
                        "request_id": (
                            request_id
                        ),
                    },
                )

            duration_ms = round(
                (
                    perf_counter()
                    - started_at
                )
                * 1_000,
                2,
            )

            route = request_route_label(
                request
            )

            if should_record_http_metrics(
                path
            ):
                record_http_request(
                    method=method,
                    route=route,
                    status_code=(
                        response.status_code
                    ),
                    duration_seconds=(
                        duration_ms
                        / 1_000
                    ),
                )

            response.headers[
                "X-Request-ID"
            ] = request_id

            if (
                path not in
                _QUIET_SUCCESS_PATHS
                or response.status_code
                >= 500
            ):
                log_method = (
                    app_logger.error
                    if response.status_code
                    >= 500
                    else app_logger.info
                )

                log_method(
                    "http_request_completed",
                    method=method,
                    path=route,
                    status_code=(
                        response.status_code
                    ),
                    duration_ms=(
                        duration_ms
                    ),
                )

            return response

        finally:
            reset_request_id(
                context_token
            )
