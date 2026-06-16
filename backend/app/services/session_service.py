from __future__ import annotations

from uuid import uuid4

from app.domain.sessions.models import ProductSessionRecord
from app.infrastructure.storage.session_repository import SessionRepository
from app.infrastructure.storage.team_repository import TeamRepository
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime
from app.runtime.agentscope.team_runtime import AgentScopeTeamRuntime
from app.services.runtime_bootstrap_service import RuntimeBootstrapService


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        team_repository: TeamRepository,
        workspace_repository: WorkspaceRepository,
        state_runtime: AgentScopeSessionStateRuntime,
        runtime_bootstrap_service: RuntimeBootstrapService,
        team_runtime: AgentScopeTeamRuntime,
        runtime_principal: str,
    ) -> None:
        self._session_repository = session_repository
        self._team_repository = team_repository
        self._workspace_repository = workspace_repository
        self._state_runtime = state_runtime
        self._runtime_bootstrap_service = runtime_bootstrap_service
        self._team_runtime = team_runtime
        self._runtime_principal = runtime_principal

    async def create_session(
        self,
        name: str,
        workspace_id: str,
        team_id: str,
    ) -> ProductSessionRecord:
        team = await self._team_repository.get_team(team_id)
        if team is None:
            raise KeyError("Team not found")
        workspace = await self._workspace_repository.get(workspace_id)
        if workspace is None:
            raise KeyError("Workspace not found")
        leader_agent = await self._team_repository.get_agent_template(team.leader_agent_id)
        if leader_agent is None:
            raise KeyError("Leader agent template not found")
        worker_agents = []
        for worker_agent_id in team.member_agent_ids:
            worker_agent = await self._team_repository.get_agent_template(worker_agent_id)
            if worker_agent is None:
                raise KeyError(f"Worker agent template not found: {worker_agent_id}")
            worker_agents.append(worker_agent)

        await self._runtime_bootstrap_service.ensure_runtime_agent(
            user_id=self._runtime_principal,
            agent_template=leader_agent,
        )
        chat_model_config = await self._runtime_bootstrap_service.build_default_chat_model_config(
            user_id=self._runtime_principal,
        )

        record = ProductSessionRecord(
            session_id=uuid4().hex,
            name=name,
            team_id=team.team_id,
            leader_agent_id=team.leader_agent_id,
            workspace_id=workspace.workspace_id,
        )
        saved = await self._session_repository.upsert(record)
        await self._state_runtime.create_runtime_session(
            user_id=self._runtime_principal,
            session_id=saved.session_id,
            agent_id=saved.leader_agent_id,
            workspace_id=saved.workspace_id,
            name=saved.name,
            chat_model_config=chat_model_config,
        )
        await self._team_runtime.ensure_runtime_team(
            product_team=team,
            leader_session_id=saved.session_id,
            worker_agent_templates=worker_agents,
            workspace_id=saved.workspace_id,
            chat_model_config=chat_model_config,
        )
        return saved
