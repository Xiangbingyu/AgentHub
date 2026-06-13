from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from agent_service.app.schemas.session import SessionCreateRequest
from agent_service.app.services.session_service import SessionService


router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_service() -> SessionService:
    return SessionService()


@router.post("")
def create_session(payload: SessionCreateRequest):
    return get_service().create(payload)


@router.post("/{session_id}/delete")
def delete_session(session_id: UUID):
    return get_service().delete(session_id)
