from __future__ import annotations

from uuid import uuid4

from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.runtime.snapshot.runtime_snapshot_resolver import RuntimeSnapshotResolver
from agent_service.app.schemas.agent_run_create import AgentRunCreateRequest, AgentRunCreateResponse


class AgentRunCreateService:
    def __init__(
        self,
        agent_repository: AgentRepository,
        agent_run_repository: AgentRunRepository,
    ) -> None:
        self.agent_repository = agent_repository
        self.agent_run_repository = agent_run_repository
        self.runtime_snapshot_resolver = RuntimeSnapshotResolver()

    def create_run(self, payload: AgentRunCreateRequest) -> AgentRunCreateResponse:
        agent = self.agent_repository.get_by_id(payload.agent_id)
        if agent is None:
            raise ValueError("agent not found")

        run_id = uuid4()
        agent_run = AgentRunModel(
            run_id=run_id,
            session_id=payload.session_id,
            agent_id=payload.agent_id,
            role=agent.role,
            agent_kind=agent.agent_kind,
            workspace_id=payload.workspace_id,
            root_run_id=run_id,
            status="created",
            context_snapshot=payload.metadata,
            runtime_snapshot=self.runtime_snapshot_resolver.build_default_snapshot(agent),
        )
        self.agent_run_repository.create(agent_run)
        return AgentRunCreateResponse(run_id=run_id, agent_id=payload.agent_id, status="created")

