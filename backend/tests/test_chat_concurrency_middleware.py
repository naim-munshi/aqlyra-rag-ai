"""ASGI chat gate: no DB/thread admission during overload, safe failures."""
import asyncio
import json

from app.middleware.chat_concurrency import ChatConcurrencyMiddleware


def _scope(path, method="POST"):
    return {"type": "http", "path": path, "method": method, "headers": []}


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def _read_status(events):
    response = next(event for event in events if event["type"] == "http.response.start")
    return response["status"], {
        bytes(k).lower(): bytes(v) for k, v in response.get("headers", [])
    }


def test_gate_queues_chat_away_from_sync_dependencies_and_rejects_excess():
    async def scenario():
        active = 0
        peak = 0
        entered = asyncio.Event()
        release = asyncio.Event()
        events_first, events_third = [], []

        async def downstream(scope, receive, send):
            nonlocal active, peak
            active += 1
            peak = max(active, peak)
            entered.set()
            try:
                await release.wait()
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b"ok"})
            finally:
                active -= 1

        gate = ChatConcurrencyMiddleware(
            downstream, max_in_flight=1, queue_timeout_seconds=0.03,
        )
        path = "/api/v1/conversations/synthetic-1/messages"
        first = asyncio.create_task(gate(_scope(path), _receive, events_first.append))
        await asyncio.wait_for(entered.wait(), timeout=1)
        await gate(_scope(path), _receive, events_third.append)
        status, headers = _read_status(events_third)
        assert status == 503
        assert headers[b"retry-after"] == b"2"
        assert headers[b"cache-control"] == b"private, no-store"
        payload = json.loads(next(
            event for event in events_third
            if event["type"] == "http.response.body"
        )["body"])
        assert "no conversation message was submitted" in payload["detail"]
        assert peak == 1
        release.set()
        await asyncio.wait_for(first, timeout=1)
        assert _read_status(events_first)[0] == 200
        # Once completed, a new request may enter normally.
        again = []
        await gate(_scope(path), _receive, again.append)
        assert _read_status(again)[0] == 200

    asyncio.run(scenario())


def test_gate_covers_streaming_chat_but_skips_other_routes():
    async def scenario():
        called = []

        async def downstream(scope, receive, send):
            called.append(scope["path"])
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"done"})

        gate = ChatConcurrencyMiddleware(
            downstream, max_in_flight=1, queue_timeout_seconds=0.1,
        )
        for path, method in (
            ("/api/v1/conversations/id/messages", "POST"),
            ("/api/v1/conversations/id/messages/stream", "POST"),
            ("/api/v1/conversations/id/messages", "GET"),
            ("/api/v1/study-abroad/cases/id/research", "POST"),
            ("/api/v1/conversations/id/messages/stream/extra", "POST"),
        ):
            events = []
            await gate(_scope(path, method), _receive, events.append)
            assert _read_status(events)[0] == 200
        assert len(called) == 5

    asyncio.run(scenario())


def test_chat_slots_are_released_on_downstream_error_or_cancellation():
    async def scenario():
        entered = asyncio.Event()

        async def failing_app(scope, receive, send):
            entered.set()
            raise RuntimeError("synthetic downstream error")

        gate = ChatConcurrencyMiddleware(
            failing_app, max_in_flight=1, queue_timeout_seconds=0.1,
        )
        for _ in range(2):
            try:
                await gate(_scope("/api/v1/conversations/id/messages"), _receive, lambda _x: None)
            except RuntimeError:
                pass
            else:
                assert False, "Downstream exception must propagate without leaking semaphore"
        assert entered.is_set()

        blocker = asyncio.Event()

        async def blocked_app(scope, receive, send):
            await blocker.wait()

        other_gate = ChatConcurrencyMiddleware(
            blocked_app, max_in_flight=1, queue_timeout_seconds=0.1,
        )
        task = asyncio.create_task(other_gate(
            _scope("/api/v1/conversations/id/messages"), _receive, lambda _x: None,
        ))
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert other_gate._slots._value == 1

    asyncio.run(scenario())
