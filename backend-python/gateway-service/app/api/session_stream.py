from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.client.agent_service_client import AgentServiceClient

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}/stream")
def session_stream(session_id: str):
    client = AgentServiceClient()
    events = client.list_session_events(session_id)

    def iterator():
        for item in events:
            yield (
                f"id: {item['sequence_no']}\n"
                f"event: {item['event_type']}\n"
                f"data: {item['payload']}\n\n"
            )

    return StreamingResponse(iterator(), media_type="text/event-stream")
