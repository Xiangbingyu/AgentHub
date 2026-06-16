from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from gateway_service.app.client.agent_service_client import AgentServiceClient

router = APIRouter(prefix="/sessions", tags=["sessions"])

# 自适应轮询：有新事件时用短间隔；连续空轮退避到较长间隔。
STREAM_ACTIVE_INTERVAL = 0.3
STREAM_IDLE_INTERVAL = 0.8
# 连续空轮上限——达到后收尾本次连接，浏览器 EventSource 会自动携带
# Last-Event-ID 重连，避免长连接无限挂起。
STREAM_MAX_IDLE_POLLS = 600


def _format_event(event: dict) -> str:
    return (
        f"id: {event['sequence_no']}\n"
        f"event: {event['event_type']}\n"
        f"data: {json.dumps(event.get('payload', {}), ensure_ascii=False)}\n\n"
    )


@router.get("/{session_id}/stream")
async def session_stream(session_id: str, request: Request):
    client = AgentServiceClient()
    last_seq = int(request.headers.get("last-event-id") or 0)

    async def iterator():
        nonlocal last_seq
        idle_polls = 0
        try:
            while idle_polls < STREAM_MAX_IDLE_POLLS:
                if await request.is_disconnected():
                    break

                events = await run_in_threadpool(
                    client.list_session_events, session_id, since=last_seq
                )
                if events:
                    idle_polls = 0
                    for event in events:
                        yield _format_event(event)
                        last_seq = event["sequence_no"]
                    await asyncio.sleep(STREAM_ACTIVE_INTERVAL)
                else:
                    idle_polls += 1
                    await asyncio.sleep(STREAM_IDLE_INTERVAL)
        except asyncio.CancelledError:
            return

    return StreamingResponse(iterator(), media_type="text/event-stream")
