from __future__ import annotations

from app.domain.workspaces.models import WorkspaceRecord
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.infrastructure.workspace.manager import WorkspacePathManager


class WorkspaceService:
    def __init__(
        self,
        repository: WorkspaceRepository,
        path_manager: WorkspacePathManager,
    ) -> None:
        self._repository = repository
        self._path_manager = path_manager

    async def create_workspace(
        self,
        name: str,
        description: str = "",
    ) -> WorkspaceRecord:
        record = self._path_manager.create_record(name=name, description=description)
        return await self._repository.upsert(record)
