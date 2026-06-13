from pathlib import Path

from agent_service.app.database.schema import initialize_schema
from agent_service.app.database.sqlite import SQLiteDatabase


def test_sqlite_database_creates_file_and_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "agenthub.db"

    database = SQLiteDatabase(str(db_path))
    conn = database.connect()

    assert db_path.exists()
    assert conn is not None


def test_initialize_schema_creates_core_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "agenthub.db"
    conn = SQLiteDatabase(str(db_path)).connect()

    initialize_schema(conn)

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {row[0] for row in rows}

    assert "agents" in names
    assert "agent_runs" in names
    assert "source_workspaces" in names
    assert "session_workspaces" in names
    assert "sessions" in names
    assert "domain_events" in names
