from __future__ import annotations

from datetime import datetime

from redis.asyncio import Redis

from app.domain.workspaces.models import WorkspaceRecord


class WorkspaceRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def upsert(self, record: WorkspaceRecord) -> WorkspaceRecord:
        await self._redis.set(
            f"agenthub:product:workspace:{record.workspace_id}",
            record.model_dump_json(),
        )
        score = float(datetime.fromisoformat(record.created_at).timestamp())
        await self._redis.zadd(
            "agenthub:product:workspaces",
            {record.workspace_id: score},
        )
        return record

    async def get(self, workspace_id: str) -> WorkspaceRecord | None:
        raw = await self._redis.get(f"agenthub:product:workspace:{workspace_id}")
        if raw is None:
            return None
        return WorkspaceRecord.model_validate_json(raw)

    async def list_all(self) -> list[WorkspaceRecord]:
        ids = await self._redis.zrevrange("agenthub:product:workspaces", 0, -1)
        records: list[WorkspaceRecord] = []
        for workspace_id in ids:
            record = await self.get(workspace_id)
            if record is not None:
                records.append(record)
        return records
