from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.session import SessionModel


class SessionRepository:
    def create(self, session: SessionModel) -> SessionModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, payload) VALUES (?, ?)",
            (str(session.session_id), session.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return session

    def get_by_id(self, session_id: UUID) -> SessionModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM sessions WHERE session_id = ?",
            (str(session_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return SessionModel.model_validate_json(row[0])

    def list_by_session_workspace_id(self, session_workspace_id: UUID) -> list[SessionModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM sessions").fetchall()
        conn.close()
        items = [SessionModel.model_validate_json(row[0]) for row in rows]
        return [item for item in items if item.session_workspace_id == session_workspace_id]

    def update(self, session: SessionModel) -> SessionModel:
        session.updated_at = datetime.now(timezone.utc)
        return self.create(session)
