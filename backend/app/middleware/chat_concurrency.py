"""Bound chat admission before sync auth/DB dependencies acquire thread tokens.

Without early ASGI admission, a burst of >AnyIO's threadpool tokens may
leave synchronous DB dependencies waiting on exhausted SQLAlchemy pool slots
while dependency cleanup itself needs worker tokens. This per-process gate
queues HTTP chat turns *without occupying* AnyIO worker threads or DB slots.

Not an account-level rate limit, horizontal/global concurrency cap, or
replacement for provider quota/budget management.
"""
import asyncio
import re

from starlette.responses import JSONResponse

_CHAT_PATH = re.compile(
    r"^/api/v1/conversations/[^/]+/messages(?:/stream)?$"
)


class ChatConcurrencyMiddleware:
    def __init__(
        self,
        app,
        *,
        max_in_flight: int,
        queue_timeout_seconds: float,
    ) -> None:
        if max_in_flight < 1 or queue_timeout_seconds <= 0:
            raise ValueError("Invalid bounded chat admission configuration")
        self.app = app
        self._slots = asyncio.BoundedSemaphore(max_in_flight)
        self._queue_timeout = queue_timeout_seconds

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or _CHAT_PATH.fullmatch(scope.get("path", "")) is None
        ):
            await self.app(scope, receive, send)
            return

        # Queueing happens in the event loop, BEFORE sync auth/session
        # dependencies. It occupies no database connection or AnyIO token.
        try:
            await asyncio.wait_for(
                self._slots.acquire(),
                timeout=self._queue_timeout,
            )
        except asyncio.TimeoutError:
            response = JSONResponse(
                {
                    "detail": (
                        "Chat is busy. Please retry shortly; "
                        "no conversation message was submitted."
                    )
                },
                status_code=503,
                headers={
                    "Retry-After": "2",
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
            await response(scope, receive, send)
            return

        try:
            # For streaming turns, hold the slot until response completes or
            # disconnects, so slow streams cannot silently bypass admission.
            await self.app(scope, receive, send)
        finally:
            self._slots.release()
