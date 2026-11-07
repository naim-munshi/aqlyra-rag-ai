"""Bound direct Render JSON requests before framework body parsing.

Frontend-side size limits alone cannot protect the publicly reachable FastAPI
ingress. This guard covers normal JSON requests (including +json and requests
without Content-Type), but deliberately leaves multipart document uploads and
binary streams to their existing streaming/file validation paths.

Authentication has a separate stricter 16 KiB limiter.
"""
from starlette.responses import JSONResponse

MAX_JSON_REQUEST_BYTES = 4 * 1024 * 1024


class JsonBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") not in ("POST", "PUT", "PATCH", "DELETE")
            or not scope.get("path", "").startswith("/api/v1/")
            or scope.get("path", "").startswith("/api/v1/auth/")
        ):
            await self.app(scope, receive, send)
            return

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        mime = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        if mime and mime != b"application/json" and not mime.endswith(b"+json"):
            # Multipart/streaming file uploads are enforced separately.
            await self.app(scope, receive, send)
            return

        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
                if size < 0 or size > MAX_JSON_REQUEST_BYTES:
                    raise ValueError("oversized")
            except (ValueError, OverflowError):
                await self._reject(scope, receive, send)
                return

        chunks = []
        total_bytes = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue

            chunk = event.get("body", b"")
            total_bytes += len(chunk)
            if total_bytes > MAX_JSON_REQUEST_BYTES:
                await self._reject(scope, receive, send)
                return

            chunks.append(chunk)
            if not event.get("more_body", False):
                break

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope, receive, send):
        response = JSONResponse(
            {"detail": "JSON request body is too large"},
            status_code=413,
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
        await response(scope, receive, send)
