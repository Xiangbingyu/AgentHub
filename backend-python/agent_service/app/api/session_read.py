from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.subtask_repository import SubtaskRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_sessions():
    return SessionRepository().list_all()


@router.get("/{session_id}")
def get_session(session_id: UUID):
    session = SessionRepository().get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.get("/{session_id}/events")
def list_session_events(session_id: UUID, since: int = Query(default=0, ge=0)):
    return DomainEventRepository().list_by_session_id_since(session_id, since=since)


@router.get("/{session_id}/subtasks")
def list_session_subtasks(session_id: UUID):
    return SubtaskRepository().list_by_session_id(session_id)
