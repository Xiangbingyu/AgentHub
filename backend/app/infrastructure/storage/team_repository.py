from __future__ import annotations

from datetime import datetime

from redis.asyncio import Redis

from app.domain.teams.models import AgentTemplateRecord, TeamRecord


class TeamRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def upsert_team(self, record: TeamRecord) -> TeamRecord:
        await self._redis.set(
            f"agenthub:product:team:{record.team_id}",
            record.model_dump_json(),
        )
        await self._redis.zadd(
            "agenthub:product:teams",
            {
                record.team_id: float(
                    datetime.fromisoformat(record.created_at).timestamp()
                )
            },
        )
        if record.is_default:
            await self._redis.set("agenthub:product:teams:default", record.team_id)
        return record

    async def upsert_agent_template(
        self,
        record: AgentTemplateRecord,
    ) -> AgentTemplateRecord:
        await self._redis.set(
            f"agenthub:product:agent-template:{record.agent_id}",
            record.model_dump_json(),
        )
        return record

    async def get_agent_template(self, agent_id: str) -> AgentTemplateRecord | None:
        raw = await self._redis.get(f"agenthub:product:agent-template:{agent_id}")
        if raw is None:
            return None
        return AgentTemplateRecord.model_validate_json(raw)

    async def get_team(self, team_id: str) -> TeamRecord | None:
        raw = await self._redis.get(f"agenthub:product:team:{team_id}")
        if raw is None:
            return None
        return TeamRecord.model_validate_json(raw)

    async def list_teams(self) -> list[TeamRecord]:
        ids = await self._redis.zrevrange("agenthub:product:teams", 0, -1)
        records: list[TeamRecord] = []
        for team_id in ids:
            record = await self.get_team(team_id)
            if record is not None:
                records.append(record)
        return records

    async def get_default_team(self) -> TeamRecord | None:
        team_id = await self._redis.get("agenthub:product:teams:default")
        if team_id is None:
            return None
        return await self.get_team(team_id)
