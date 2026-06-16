from __future__ import annotations

from datetime import datetime

from redis.asyncio import Redis

from app.domain.sessions.models import ProductSessionRecord


class SessionRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, session_id: str) -> str:
        return f"agenthub:product:session:{session_id}"

    async def upsert(self, record: ProductSessionRecord) -> ProductSessionRecord:
        await self._redis.set(self._key(record.session_id), record.model_dump_json())
        score = float(datetime.fromisoformat(record.created_at).timestamp())
        await self._redis.zadd("agenthub:product:sessions", {record.session_id: score})
        return record

    async def get(self, session_id: str) -> ProductSessionRecord | None:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        return ProductSessionRecord.model_validate_json(raw)

    async def list_all(self) -> list[ProductSessionRecord]:
        ids = await self._redis.zrevrange("agenthub:product:sessions", 0, -1)
        records: list[ProductSessionRecord] = []
        for session_id in ids:
            record = await self.get(session_id)
            if record is not None:
                records.append(record)
        return records
