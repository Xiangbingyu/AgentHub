from uuid import uuid4

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.main import app
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository

client = TestClient(app)


def test_get_agent_run_returns_detail_and_404() -> None:
    bootstrap_memory_store()
    run = AgentRunRepository().create(
        AgentRunModel(
            run_id=uuid4(),
            session_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="orchestrator",
            workspace_id=uuid4(),
            status="chatting",
        )
    )

    ok = client.get(f"/agent-runs/{run.run_id}")
    assert ok.status_code == 200
    body = ok.json()
    assert body["run_id"] == str(run.run_id)
    assert body["status"] == "chatting"

    assert client.get(f"/agent-runs/{uuid4()}").status_code == 404
