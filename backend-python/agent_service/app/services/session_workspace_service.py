from __future__ import annotations

from uuid import uuid4

from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.schemas.session_workspace import SessionWorkspaceCreateRequest, SessionWorkspaceResponse


class SessionWorkspaceService:
    def __init__(self, repository: SessionWorkspaceRepository | None = None) -> None:
        self.repository = repository or SessionWorkspaceRepository()

    def create(self, payload: SessionWorkspaceCreateRequest) -> SessionWorkspaceResponse:
        workspace = SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=payload.source_workspace_id,
            name=payload.name,
            root_path=payload.root_path,
            status="ready",
        )
        self.repository.create(workspace)
        return SessionWorkspaceResponse.model_validate(workspace.model_dump())
