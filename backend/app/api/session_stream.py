from __future__ import annotations

import asyncio
from contextlib import suppress

from agentscope.app.message_bus import RedisMessageBus
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.stream.sse import encode_sse

session_stream_router = APIRouter(prefix="/sessions", tags=["session-stream"])

_HEARTBEAT_INTERVAL_SECS = 30


@session_stream_router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request) -> StreamingResponse:
    async def event_generator():
        redis = get_redis_client()
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with message_bus:
            yield encode_sse(
                "session.ready",
                {"session_id": session_id, "status": "connected"},
            )

            queue: asyncio.Queue[dict | None] = asyncio.Queue()

            async def feeder() -> None:
                try:
                    async for event in message_bus.session_subscribe_events(session_id):
                        await queue.put(event)
                except asyncio.CancelledError:
                    pass
                finally:
                    await queue.put(None)

            feeder_task = asyncio.create_task(feeder(), name=f"session-stream:{session_id}")

            for _entry_id, event in await message_bus.session_read_events(session_id):
                yield encode_sse("session.event", event)

            # Drain queued wakeups only after the live subscription is attached,
            # so callback-driven hint events are not lost between publish and replay trim.
            await request.app.state.services.runtime_bundle.drain_wakeups_once()

            try:
                while True:
                    try:
                        item = await asyncio.wait_for(
                            queue.get(),
                            timeout=_HEARTBEAT_INTERVAL_SECS,
                        )
                        if item is None:
                            break
                        yield encode_sse("session.event", item)
                    except asyncio.TimeoutError:
                        yield ":\n\n"
            finally:
                feeder_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await asyncio.wait_for(feeder_task, timeout=0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
