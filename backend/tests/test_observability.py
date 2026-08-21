import re

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.logging import app_logger
from app.middleware.observability import (
    setup_request_observability,
)


_REQUEST_ID_RE = re.compile(
    r"^[A-Fa-f0-9]{32}$"
)


def build_app() -> FastAPI:
    test_app = FastAPI()

    setup_request_observability(
        test_app
    )

    @test_app.get("/ok")
    async def ok():
        return {
            "ok": True,
        }

    @test_app.get(
        "/api/v1/readiness"
    )
    async def readiness():
        return {
            "status": "ready",
        }

    @test_app.post("/echo")
    async def echo(
        request: Request,
    ):
        await request.body()

        return {
            "ok": True,
        }

    @test_app.get("/explode")
    async def explode():
        raise RuntimeError(
            "TOP-SECRET-EXCEPTION-VALUE"
        )

    return test_app


def capture_records():
    records: list[dict] = []

    sink_id = app_logger.add(
        lambda message: (
            records.append(
                message.record
            )
        )
    )

    return records, sink_id


def test_generated_request_id_is_returned_and_logged(
) -> None:
    test_app = build_app()

    records, sink_id = (
        capture_records()
    )

    try:
        client = TestClient(
            test_app
        )

        response = client.get(
            "/ok"
        )

    finally:
        app_logger.remove(
            sink_id
        )

    assert response.status_code == 200

    request_id = (
        response.headers[
            "x-request-id"
        ]
    )

    assert _REQUEST_ID_RE.fullmatch(
        request_id
    )

    completed = [
        record
        for record in records
        if (
            record["message"]
            == "http_request_completed"
        )
    ]

    assert len(completed) == 1

    assert (
        completed[0]["extra"][
            "request_id"
        ]
        == request_id
    )


def test_safe_supplied_request_id_is_preserved(
) -> None:
    test_app = build_app()

    client = TestClient(
        test_app
    )

    response = client.get(
        "/ok",
        headers={
            "X-Request-ID": (
                "client-request-123456"
            ),
        },
    )

    assert (
        response.headers[
            "x-request-id"
        ]
        == "client-request-123456"
    )


def test_invalid_request_id_is_replaced(
) -> None:
    test_app = build_app()

    client = TestClient(
        test_app
    )

    response = client.get(
        "/ok",
        headers={
            "X-Request-ID":
                "invalid request id",
        },
    )

    request_id = (
        response.headers[
            "x-request-id"
        ]
    )

    assert request_id != (
        "invalid request id"
    )

    assert _REQUEST_ID_RE.fullmatch(
        request_id
    )


def test_query_string_and_body_are_not_logged(
) -> None:
    test_app = build_app()

    records, sink_id = (
        capture_records()
    )

    try:
        client = TestClient(
            test_app
        )

        response = client.post(
            "/echo"
            "?token="
            "TOP-SECRET-QUERY",
            content=(
                b"TOP-SECRET-BODY"
            ),
        )

    finally:
        app_logger.remove(
            sink_id
        )

    assert response.status_code == 200

    serialized = repr(
        records
    )

    assert (
        "TOP-SECRET-QUERY"
        not in serialized
    )

    assert (
        "TOP-SECRET-BODY"
        not in serialized
    )


def test_unhandled_exception_is_generic_and_correlated(
) -> None:
    test_app = build_app()

    records, sink_id = (
        capture_records()
    )

    try:
        client = TestClient(
            test_app,
            raise_server_exceptions=False,
        )

        response = client.get(
            "/explode"
        )

    finally:
        app_logger.remove(
            sink_id
        )

    assert response.status_code == 500

    request_id = (
        response.headers[
            "x-request-id"
        ]
    )

    assert response.json() == {
        "detail":
            "Internal server error",
        "request_id":
            request_id,
    }

    assert (
        "TOP-SECRET-EXCEPTION-VALUE"
        not in response.text
    )

    exception_records = [
        record
        for record in records
        if (
            record["message"]
            == (
                "http_request_"
                "unhandled_exception"
            )
        )
    ]

    assert len(
        exception_records
    ) == 1

    assert (
        exception_records[0][
            "extra"
        ][
            "request_id"
        ]
        == request_id
    )


def test_successful_readiness_is_not_application_logged(
) -> None:
    test_app = build_app()

    records, sink_id = (
        capture_records()
    )

    try:
        client = TestClient(
            test_app
        )

        response = client.get(
            "/api/v1/readiness"
        )

    finally:
        app_logger.remove(
            sink_id
        )

    assert response.status_code == 200

    assert not any(
        record["message"]
        == "http_request_completed"
        for record in records
    )
