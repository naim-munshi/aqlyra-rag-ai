"""Bound public identity JSON requests before FastAPI buffers and validates them.

The API is reachable directly at Render; Vercel-only limits cannot protect
that ingress. This ASGI wrapper reads at most 16 KiB of an identity request
and replays the small body to FastAPI. Normal uploads and streams are not
buffered here.
"""
from starlette.responses import JSONResponse

_MAX_AUTH_BYTES = 16_384


class AuthenticationBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") not in ("POST", "PUT", "PATCH")
            or not scope.get("path", "").startswith("/api/v1/auth/")
        ):
            await self.app(scope, receive, send)
            return

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
                if size < 0 or size > _MAX_AUTH_BYTES:
                    raise ValueError("oversized")
            except (ValueError, OverflowError):
                await self._reject(scope, receive, send)
                return

        parts = []
        total = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            chunk = event.get("body", b"")
            total += len(chunk)
            if total > _MAX_AUTH_BYTES:
                await self._reject(scope, receive, send)
                return
            parts.append(chunk)
            if not event.get("more_body", False):
                break

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": b"".join(parts),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope, receive, send):
        response = JSONResponse(
            {"detail": "Authentication request is too large"},
            status_code=413,
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
        await response(scope, receive, send)
