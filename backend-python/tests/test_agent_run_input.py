from pathlib import Path
from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.main import app


client = TestClient(app)


def test_orchestrator_input_generates_markdown_plan_file() -> None:
    bootstrap_memory_store()

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
            "payload": {
                "content": (
                    "Create an execution plan for implementing a markdown export feature in a Python "
                    "backend. Use the plan_tool now."
                )
            },
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}
    assert STORE.agent_runs[UUID(run_id)].status == "chatting"
    plan_file = Path(STORE.plans[UUID(run_id)].file_path)
    assert plan_file.exists()
    assert plan_file.suffix == ".md"
    assert plan_file.read_text(encoding="utf-8").strip()


def test_worker_callback_input_agent_run() -> None:
    bootstrap_memory_store()

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
