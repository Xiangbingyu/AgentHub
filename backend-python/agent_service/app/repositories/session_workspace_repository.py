from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.session_workspace import SessionWorkspaceModel


class SessionWorkspaceRepository:
    def create(self, workspace: SessionWorkspaceModel) -> SessionWorkspaceModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO session_workspaces (session_workspace_id, payload) VALUES (?, ?)",
            (str(workspace.session_workspace_id), workspace.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return workspace

    def get_by_id(self, session_workspace_id: UUID) -> SessionWorkspaceModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM session_workspaces WHERE session_workspace_id = ?",
            (str(session_workspace_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return SessionWorkspaceModel.model_validate_json(row[0])

    def list_by_source_workspace_id(self, source_workspace_id: UUID) -> list[SessionWorkspaceModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM session_workspaces").fetchall()
        conn.close()
        items = [SessionWorkspaceModel.model_validate_json(row[0]) for row in rows]
        return [item for item in items if item.source_workspace_id == source_workspace_id]

    def update(self, workspace: SessionWorkspaceModel) -> SessionWorkspaceModel:
        workspace.updated_at = datetime.now(timezone.utc)
        return self.create(workspace)
