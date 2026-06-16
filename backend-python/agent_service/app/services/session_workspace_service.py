from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID, uuid4

from agent_service.app.config import get_settings
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository
from agent_service.app.schemas.session_workspace import (
    SessionWorkspaceCreateRequest,
    SessionWorkspaceResponse,
)


class SessionWorkspaceService:
    def __init__(
        self,
        repository: SessionWorkspaceRepository | None = None,
        source_repository: SourceWorkspaceRepository | None = None,
    ) -> None:
        self.repository = repository or SessionWorkspaceRepository()
        self.source_repository = source_repository or SourceWorkspaceRepository()

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

    def derive_from_source(
        self, source_workspace_id: UUID, name: str | None = None
    ) -> SessionWorkspaceResponse:
        """基于 source workspace 派生一个隔离副本（本地目录全量复制，不复用）。"""
        source = self.source_repository.get_by_id(source_workspace_id)
        if source is None:
            raise ValueError(f"source workspace not found: {source_workspace_id}")

        src_root = Path(source.root_path).expanduser()
        if not src_root.is_dir():
            raise ValueError(f"source root_path is not a directory: {source.root_path}")

        new_id = uuid4()
        dest = Path(get_settings().session_workspace_root).expanduser() / str(new_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_root, dest)

        workspace = SessionWorkspaceModel(
            session_workspace_id=new_id,
            source_workspace_id=source.source_workspace_id,
            name=name or f"{source.name}-{new_id.hex[:8]}",
            root_path=str(dest),
            status="ready",
            origin_session_workspace_id=None,
        )
        self.repository.create(workspace)
        return SessionWorkspaceResponse.model_validate(workspace.model_dump())
