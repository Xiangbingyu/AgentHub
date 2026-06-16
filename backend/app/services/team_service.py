from __future__ import annotations

from uuid import uuid4

from app.domain.teams.models import AgentTemplateRecord, ModelConfig, TeamRecord
from app.infrastructure.storage.team_repository import TeamRepository


def _default_leader_template() -> AgentTemplateRecord:
    return AgentTemplateRecord(
        agent_id="default-leader-agent",
        name="Default Leader",
        role="leader",
        system_prompt="You are the default leader agent for AgentHub.",
        default_model_config=ModelConfig(provider="dashscope", model="qwen3.6-plus"),
    )


class TeamService:
    def __init__(self, repository: TeamRepository) -> None:
        self._repository = repository

    async def ensure_default_team(self) -> TeamRecord:
        existing = await self._repository.get_default_team()
        if existing is not None:
            return existing
        await self._repository.upsert_agent_template(_default_leader_template())
        default_team = TeamRecord(
            team_id=uuid4().hex,
            name="Default Team",
            description="System-provided default team.",
            leader_agent_id="default-leader-agent",
            member_agent_ids=[],
            is_default=True,
        )
        return await self._repository.upsert_team(default_team)

    async def create_team(
        self,
        name: str,
        leader_agent_id: str,
        member_agent_ids: list[str],
        description: str = "",
    ) -> TeamRecord:
        await self._repository.upsert_agent_template(
            AgentTemplateRecord(
                agent_id=leader_agent_id,
                name=leader_agent_id,
                role="leader",
                system_prompt=f"You are {leader_agent_id}, the leader agent for team {name}.",
                default_model_config=ModelConfig(
                    provider="dashscope",
                    model="qwen3.6-plus",
                ),
            )
        )
        for member_agent_id in member_agent_ids:
            await self._repository.upsert_agent_template(
                AgentTemplateRecord(
                    agent_id=member_agent_id,
                    name=member_agent_id,
                    role="worker",
                    system_prompt=f"You are {member_agent_id}, a worker agent for team {name}.",
                    default_model_config=ModelConfig(
                        provider="dashscope",
                        model="qwen3.6-plus",
                    ),
                )
            )
        team = TeamRecord(
            team_id=uuid4().hex,
            name=name,
            description=description,
            leader_agent_id=leader_agent_id,
            member_agent_ids=member_agent_ids,
        )
        return await self._repository.upsert_team(team)
