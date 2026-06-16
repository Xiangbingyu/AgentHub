from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 在任何测试模块导入 app（其 create_app() 会在导入期 bootstrap 数据库）之前，
# 把 SQLite 指向临时文件，避免测试污染开发库、并保证用例间隔离。
_TEST_DB_DIR = tempfile.mkdtemp(prefix="agenthub-test-")
os.environ["SQLITE_DB_PATH"] = str(Path(_TEST_DB_DIR) / "test.db")

import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _ensure_schema() -> None:
    """保证临时库已建表。

    走 app 启动（TestClient）的用例会在 bootstrap 时建表，但只用 repository 的
    用例不经过启动流程，需要在此显式初始化 schema，否则会 "no such table"。
    initialize_schema 用 CREATE TABLE IF NOT EXISTS，重复调用安全。
    """
    from agent_service.app.config import get_settings
    from agent_service.app.database.schema import initialize_schema
    from agent_service.app.database.sqlite import SQLiteDatabase

    conn = SQLiteDatabase(get_settings().sqlite_db_path).connect()
    initialize_schema(conn)
    conn.close()
