from __future__ import annotations

from pathlib import Path

from agentscope.app.workspace_manager._base import WorkspaceManagerBase
from agentscope.workspace import LocalWorkspace


class WorkspaceRuntimeManager(WorkspaceManagerBase):
    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()

    async def get_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        workspace_id: str,
    ) -> LocalWorkspace:
        del user_id, agent_id, session_id
        workspace = LocalWorkspace(
            workspace_id=workspace_id,
            workdir=str(self._base_dir / workspace_id),
        )
        await workspace.initialize()
        return workspace

    async def create_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
    ) -> LocalWorkspace:
        del user_id, agent_id, session_id
        workspace = LocalWorkspace(workdir=str(self._base_dir))
        await workspace.initialize()
        return workspace

    async def close(self, workspace_id: str) -> None:
        del workspace_id

    async def close_all(self) -> None:
        return None


class WorkspaceRuntime:
    async def build_local_workspace(
        self,
        root_path: str,
        workspace_id: str,
    ) -> LocalWorkspace:
        workspace = LocalWorkspace(workspace_id=workspace_id, workdir=root_path)
        await workspace.initialize()
        return workspace
