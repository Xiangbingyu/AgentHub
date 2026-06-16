from __future__ import annotations

import json

from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.infrastructure.workspace.file_browser import WorkspaceFileBrowser


class WorkspaceQueryService:
    def __init__(
        self,
        repository: WorkspaceRepository,
        file_browser: WorkspaceFileBrowser,
    ) -> None:
        self._repository = repository
        self._file_browser = file_browser

    async def list_workspaces(self) -> dict:
        records = await self._repository.list_all()
        return {"workspaces": [record.model_dump(mode="json") for record in records]}

    async def get_tree(self, workspace_id: str, path: str = "") -> dict:
        record = await self._repository.get(workspace_id)
        if record is None:
            raise KeyError(workspace_id)
        entries = self._file_browser.list_tree(record.root_path, path)
        return {"workspace_id": workspace_id, "path": path, "entries": entries}

    async def read_file(self, workspace_id: str, path: str) -> dict:
        record = await self._repository.get(workspace_id)
        if record is None:
            raise KeyError(workspace_id)
        content = self._file_browser.read_file(record.root_path, path)
        return {"workspace_id": workspace_id, "path": path, "content": content}

    async def read_plan_snapshot(self, workspace_id: str) -> dict | None:
        record = await self._repository.get(workspace_id)
        if record is None:
            raise KeyError(workspace_id)
        try:
            content = self._file_browser.read_file(record.root_path, "plan/current-plan.json")
        except ValueError:
            return None
        return json.loads(content)
