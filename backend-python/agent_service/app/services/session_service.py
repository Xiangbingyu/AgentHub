from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from agent_service.app.models.domain_event import DomainEventModel
from agent_service.app.models.session import SessionModel
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.schemas.session import SessionCreateRequest, SessionResponse


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        session_workspace_repository: SessionWorkspaceRepository | None = None,
        domain_event_repository: DomainEventRepository | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.session_workspace_repository = session_workspace_repository or SessionWorkspaceRepository()
        self.domain_event_repository = domain_event_repository or DomainEventRepository()

    def create(self, payload: SessionCreateRequest) -> SessionResponse:
        session_workspace = self.session_workspace_repository.get_by_id(payload.session_workspace_id)
        if session_workspace is None:
            raise ValueError("session workspace not found")
        if session_workspace.status != "ready":
            raise ValueError("session workspace is not available")

        session = SessionModel(
            session_id=uuid4(),
            session_workspace_id=payload.session_workspace_id,
            title=payload.title,
            status="active",
        )
        self.session_repository.create(session)
        self.session_workspace_repository.update(
            session_workspace.model_copy(update={"status": "attached"})
        )
        sequence_no = self.domain_event_repository.next_sequence_no(session.session_id)
        self.domain_event_repository.create(
            DomainEventModel(
                event_id=uuid4(),
                session_id=session.session_id,
                session_workspace_id=session.session_workspace_id,
                event_type="session.message.appended",
                event_scope="main_timeline",
                sequence_no=sequence_no,
                payload={"content": session.title, "kind": "session_created"},
            )
        )
        return SessionResponse.model_validate(session.model_dump())

    def delete(self, session_id: UUID) -> SessionResponse:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ValueError("session not found")

        workspace = self.session_workspace_repository.get_by_id(session.session_workspace_id)
        if workspace is not None:
            self.session_workspace_repository.update(workspace.model_copy(update={"status": "ready"}))

        deleted = session.model_copy(
            update={
                "status": "deleted",
                "deleted_at": datetime.now(timezone.utc),
            }
        )
        self.session_repository.update(deleted)
        return SessionResponse.model_validate(deleted.model_dump())
