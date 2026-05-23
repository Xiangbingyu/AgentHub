from __future__ import annotations

from uuid import uuid4

from app.models.agent_run import AgentRunModel
from app.models.plan import PlanModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.agent_run_create import AgentRunCreateRequest, AgentRunCreateResponse


class AgentRunCreateService:
    def __init__(
        self,
        agent_repository: AgentRepository,
        agent_run_repository: AgentRunRepository,
        plan_repository: PlanRepository,
    ) -> None:
        self.agent_repository = agent_repository
        self.agent_run_repository = agent_run_repository
        self.plan_repository = plan_repository

    def create_run(self, payload: AgentRunCreateRequest) -> AgentRunCreateResponse:
        agent = self.agent_repository.get_by_id(payload.agent_id)
        if agent is None:
            raise ValueError("agent not found")

        run_id = uuid4()
        agent_run = AgentRunModel(
            run_id=run_id,
            agent_id=payload.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=payload.workspace_id,
            root_run_id=run_id,
            status="created",
            context_snapshot=payload.metadata,
        )
        self.agent_run_repository.create(agent_run)
        self.plan_repository.create(
            PlanModel(
                plan_id=uuid4(),
                run_id=run_id,
                workspace_id=payload.workspace_id,
                raw_document="",
                file_path=str(__import__("pathlib").Path.cwd() / ".AgentHub" / "plans" / f"{run_id}.execution-plan.md"),
                status="pending",
                summary="",
            )
        )
        return AgentRunCreateResponse(run_id=run_id, agent_id=payload.agent_id, status="created")
