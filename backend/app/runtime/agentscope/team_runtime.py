from __future__ import annotations

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app.storage import RedisStorage
from agentscope.app.storage._model._agent import AgentData, AgentRecord
from agentscope.app.storage._model._session import ChatModelConfig, SessionConfig
from agentscope.app.storage._model._team import TeamData, TeamRecord
from agentscope.state import AgentState
from redis.asyncio import Redis

from app.domain.teams.models import AgentTemplateRecord
from app.domain.teams.models import TeamRecord as ProductTeamRecord


class AgentScopeTeamRuntime:
    def __init__(self, redis: Redis, runtime_principal: str) -> None:
        self._redis = redis
        self._runtime_principal = runtime_principal

    @staticmethod
    def build_worker_session_id(product_session_id: str, worker_agent_id: str) -> str:
        return f"{product_session_id}:{worker_agent_id}"

    async def ensure_runtime_team(
        self,
        *,
        product_team: ProductTeamRecord,
        leader_session_id: str,
        worker_agent_templates: list[AgentTemplateRecord],
        workspace_id: str,
        chat_model_config: ChatModelConfig | None,
    ) -> None:
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            runtime_team = await storage.get_team(self._runtime_principal, product_team.team_id)
            if runtime_team is None:
                runtime_team = TeamRecord(
                    id=product_team.team_id,
                    user_id=self._runtime_principal,
                    session_id=leader_session_id,
                    data=TeamData(
                        name=product_team.name,
                        description=product_team.description,
                        member_ids=[],
                    ),
                )
            else:
                runtime_team.session_id = leader_session_id
                runtime_team.data.name = product_team.name
                runtime_team.data.description = product_team.description

            await storage.upsert_team(self._runtime_principal, runtime_team)
            await storage.set_session_team_id(
                self._runtime_principal,
                leader_session_id,
                runtime_team.id,
            )

            member_ids: list[str] = []
            for worker_agent in worker_agent_templates:
                await self._ensure_worker_agent(
                    storage=storage,
                    worker_agent=worker_agent,
                )
                worker_session_id = await self._ensure_worker_session(
                    storage=storage,
                    product_session_id=leader_session_id,
                    worker_agent_id=worker_agent.agent_id,
                    workspace_id=workspace_id,
                    chat_model_config=chat_model_config,
                    team_id=runtime_team.id,
                    team_name=product_team.name,
                )
                member_ids.append(worker_agent.agent_id)
                await storage.set_session_team_id(
                    self._runtime_principal,
                    worker_session_id,
                    runtime_team.id,
                )

            runtime_team.data.member_ids = member_ids
            await storage.upsert_team(self._runtime_principal, runtime_team)

    async def _ensure_worker_agent(
        self,
        *,
        storage: RedisStorage,
        worker_agent: AgentTemplateRecord,
    ) -> None:
        record = AgentRecord(
            id=worker_agent.agent_id,
            user_id=self._runtime_principal,
            source="team",
            data=AgentData(
                id=worker_agent.agent_id,
                name=worker_agent.name,
                system_prompt=worker_agent.system_prompt,
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )
        await storage.upsert_agent(self._runtime_principal, record)

    async def _ensure_worker_session(
        self,
        *,
        storage: RedisStorage,
        product_session_id: str,
        worker_agent_id: str,
        workspace_id: str,
        chat_model_config: ChatModelConfig | None,
        team_id: str,
        team_name: str,
    ) -> str:
        worker_session_id = self.build_worker_session_id(product_session_id, worker_agent_id)
        await storage.upsert_session(
            user_id=self._runtime_principal,
            agent_id=worker_agent_id,
            config=SessionConfig(
                workspace_id=workspace_id,
                name=f"team:{team_name}/{worker_agent_id}",
                chat_model_config=chat_model_config,
                fallback_chat_model_config=None,
            ),
            state=AgentState(),
            session_id=worker_session_id,
        )
        await storage.set_session_team_id(
            self._runtime_principal,
            worker_session_id,
            team_id,
        )
        return worker_session_id
