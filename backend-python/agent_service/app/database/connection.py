from __future__ import annotations

from agent_service.app.config import get_settings
from agent_service.app.database.sqlite import SQLiteDatabase


def get_connection():
    settings = get_settings()
    return SQLiteDatabase(settings.sqlite_db_path).connect()
