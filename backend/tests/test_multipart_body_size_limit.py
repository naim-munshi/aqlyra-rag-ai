"""Regression tests for the complete multipart ingress envelope limit."""
import asyncio

from app.middleware.multipart_body_limit import MultipartBodyLimitMiddleware


def _run_request(*, headers, chunks, path="/api/v1/documents/upload", method="POST"):
    events = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]
    responses = []

    async def receive():
        if events:
            return events.pop(0)
        return {"type": "http.disconnect"}

    async def send(message):
        responses.append(message)

    async def downstream(scope, inner_receive, inner_send):
        while True:
            message = await inner_receive()
            if message.get("type") != "http.request" or not message.get("more_body", False):
                break
        await inner_send({"type": "http.response.start", "status": 200, "headers": []})
        await inner_send({"type": "http.response.body", "body": b"ok", "more_body": False})

    app = MultipartBodyLimitMiddleware(
        downstream,
        max_body_bytes=10,
        upload_path="/api/v1/documents/upload",
    )
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
    }
    asyncio.run(app(scope, receive, send))
    return responses


def _status(responses):
    return next(item["status"] for item in responses if item["type"] == "http.response.start")


def test_declared_oversized_multipart_body_rejected_before_parser():
    responses = _run_request(
        headers=[
            (b"content-type", b"multipart/form-data; boundary=test"),
            (b"content-length", b"11"),
        ],
        chunks=[],
    )
    assert _status(responses) == 413


def test_chunked_multipart_body_without_content_length_is_bounded():
    responses = _run_request(
        headers=[(b"content-type", b"multipart/form-data; boundary=test")],
        chunks=[b"12345", b"67890"],
    )
    assert _status(responses) == 413
    body = next(item["body"] for item in responses if item["type"] == "http.response.body")
    assert b"Multipart upload body is too large" in body


def test_forged_small_content_length_does_not_bypass_multipart_cap():
    responses = _run_request(
        headers=[
            (b"content-type", b"multipart/form-data; boundary=test"),
            (b"content-length", b"1"),
        ],
        chunks=[b"123456", b"78901"],
    )
    assert _status(responses) == 413


def test_non_upload_routes_keep_existing_request_handling():
    responses = _run_request(
        headers=[(b"content-type", b"multipart/form-data; boundary=test")],
        chunks=[b"x" * 40],
        path="/api/v1/other",
    )
    assert _status(responses) == 200
