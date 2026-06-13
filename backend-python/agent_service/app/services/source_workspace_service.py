from __future__ import annotations

from uuid import uuid4

from agent_service.app.models.source_workspace import SourceWorkspaceModel
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository
from agent_service.app.schemas.source_workspace import SourceWorkspaceCreateRequest, SourceWorkspaceResponse


class SourceWorkspaceService:
    def __init__(self, repository: SourceWorkspaceRepository | None = None) -> None:
        self.repository = repository or SourceWorkspaceRepository()

    def create(self, payload: SourceWorkspaceCreateRequest) -> SourceWorkspaceResponse:
        workspace = SourceWorkspaceModel(
            source_workspace_id=uuid4(),
            name=payload.name,
            root_path=payload.root_path,
            status="ready",
        )
        self.repository.create(workspace)
        return SourceWorkspaceResponse.model_validate(workspace.model_dump())
