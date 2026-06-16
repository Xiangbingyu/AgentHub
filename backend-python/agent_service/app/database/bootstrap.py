from __future__ import annotations

from agent_service.app.config import get_settings
from agent_service.app.database.memory_store import STORE
from agent_service.app.database.schema import initialize_schema
from agent_service.app.database.seed import seed_memory_store
from agent_service.app.database.sqlite import SQLiteDatabase
from agent_service.app.repositories.agent_repository import AgentRepository


def bootstrap_memory_store() -> None:
    settings = get_settings()
    conn = SQLiteDatabase(settings.sqlite_db_path).connect()
    initialize_schema(conn)
    conn.close()

    STORE.reset()
    # 先把持久化的 agent 载回内存，再按需 seed（已存在则跳过）。
    AgentRepository().warm_cache()
    seed_memory_store()
