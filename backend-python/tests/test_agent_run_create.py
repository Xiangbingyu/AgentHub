from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from app.database.memory_store import STORE
from app.main import app


client = TestClient(app)


def test_create_agent_run() -> None:
    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert "run_id" in body
    created_run = STORE.agent_runs[UUID(body["run_id"])]
    assert created_run.runtime_snapshot["role"] == "orchestrator"
