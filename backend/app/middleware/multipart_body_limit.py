"""Bound direct multipart uploads before Starlette parses/spools their body.

The file service still enforces the per-file byte limit while streaming to disk.
This outer ASGI guard additionally caps the complete multipart envelope, including
chunked requests with a missing or dishonest Content-Length header.
"""
from __future__ import annotations

import json

class _MultipartBodyTooLarge(Exception):
    """Internal signal raised before an oversized body reaches the parser."""


class MultipartBodyLimitMiddleware:
    def __init__(
        self,
        app,
        *,
        max_body_bytes: int,
        upload_path: str,
    ) -> None:
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.upload_path = upload_path

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != self.upload_path
        ):
            await self.app(scope, receive, send)
            return

        headers = {
            name.lower(): value
            for name, value in scope.get("headers", [])
        }
        content_type = headers.get(b"content-type", b"")
        mime = content_type.split(b";", 1)[0].strip().lower()
        if mime != b"multipart/form-data":
            await self.app(scope, receive, send)
            return

        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                declared_size = int(declared)
            except (TypeError, ValueError, OverflowError):
                await self._reject(send)
                return
            if declared_size < 0 or declared_size > self.max_body_bytes:
                await self._reject(send)
                return

        received_bytes = 0
        response_started = False

        async def guarded_receive():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise _MultipartBodyTooLarge
            return message

        async def guarded_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, guarded_receive, guarded_send)
        except _MultipartBodyTooLarge:
            # FastAPI/Starlette must parse the full form before entering the
            # upload endpoint, so overflow is expected before response start.
            if not response_started:
                await self._reject(send)

    async def _reject(self, send) -> None:
        body = json.dumps(
            {"detail": "Multipart upload body is too large"},
            separators=(",", ":"),
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"private, no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        })
