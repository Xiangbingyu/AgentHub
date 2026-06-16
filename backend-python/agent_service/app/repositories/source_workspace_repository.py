from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.source_workspace import SourceWorkspaceModel


class SourceWorkspaceRepository:
    def create(self, workspace: SourceWorkspaceModel) -> SourceWorkspaceModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO source_workspaces (source_workspace_id, payload) VALUES (?, ?)",
            (str(workspace.source_workspace_id), workspace.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return workspace

    def get_by_id(self, source_workspace_id: UUID) -> SourceWorkspaceModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM source_workspaces WHERE source_workspace_id = ?",
            (str(source_workspace_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return SourceWorkspaceModel.model_validate_json(row[0])

    def list_all(self) -> list[SourceWorkspaceModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM source_workspaces").fetchall()
        conn.close()
        return [SourceWorkspaceModel.model_validate_json(row[0]) for row in rows]

    def update(self, workspace: SourceWorkspaceModel) -> SourceWorkspaceModel:
        workspace.updated_at = datetime.now(timezone.utc)
        return self.create(workspace)
