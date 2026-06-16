from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.domain.workspaces.models import WorkspaceRecord


class WorkspacePathManager:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self._base_dir = Path(base_dir or settings.workspace_base_dir).resolve()

    def create_record(self, name: str, description: str = "") -> WorkspaceRecord:
        workspace_id = uuid4().hex
        root_path = self._base_dir / workspace_id
        root_path.mkdir(parents=True, exist_ok=True)
        return WorkspaceRecord(
            workspace_id=workspace_id,
            name=name,
            description=description,
            root_path=str(root_path),
        )
