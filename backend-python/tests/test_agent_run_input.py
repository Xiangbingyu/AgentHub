from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from app.database.memory_store import STORE
from app.main import app


client = TestClient(app)


def test_input_agent_run() -> None:
    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/agent-runs/{run_id}/input",
        json={
            "input_id": str(uuid4()),
            "type": "user_input",
            "payload": {"content": "please help"},
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}
    assert STORE.agent_runs[UUID(run_id)].status == "chatting"
    assert STORE.plans[UUID(run_id)].summary


def test_worker_callback_input_agent_run() -> None:
    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "worker")
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/agent-runs/{run_id}/input",
        json={
            "input_id": str(uuid4()),
            "type": "worker_callback",
            "payload": {"summary": "done"},
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}
