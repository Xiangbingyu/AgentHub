from __future__ import annotations

from agent_service.app.config import get_settings
from agent_service.app.database.memory_store import STORE
from agent_service.app.database.schema import initialize_schema
from agent_service.app.database.seed import seed_memory_store
from agent_service.app.database.sqlite import SQLiteDatabase


def bootstrap_memory_store() -> None:
    settings = get_settings()
    conn = SQLiteDatabase(settings.sqlite_db_path).connect()
    initialize_schema(conn)
    conn.close()

    STORE.reset()
    seed_memory_store()
