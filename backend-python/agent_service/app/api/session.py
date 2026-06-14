from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_service.app.schemas.session import SessionCreateRequest, SessionFromSourceRequest
from agent_service.app.services.session_message_service import SessionMessageService
from agent_service.app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionMessageRequest(BaseModel):
    content: str


def get_service() -> SessionService:
    return SessionService()


@router.post("")
def create_session(payload: SessionCreateRequest):
    return get_service().create(payload)


@router.post("/from-source")
def create_session_from_source(payload: SessionFromSourceRequest):
    try:
        return get_service().create_from_source(payload.source_workspace_id, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{session_id}/delete")
def delete_session(session_id: UUID):
    return get_service().delete(session_id)


@router.post("/{session_id}/messages")
def post_session_message(session_id: UUID, payload: SessionMessageRequest):
    try:
        return SessionMessageService().send(session_id, content=payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
