from fastapi.testclient import TestClient

from app.domain.sessions.models import ProductSessionRecord, WaitingItem
from app.domain.workspaces.models import WorkspaceRecord
from app.main import create_app


def test_product_session_record_defaults() -> None:
    record = ProductSessionRecord(
        session_id="session-1",
        name="Demo",
        team_id="team-1",
        leader_agent_id="agent-1",
        workspace_id="workspace-1",
    )

    assert record.status == "idle"
    assert record.waiting_items == []
    assert record.agent_statuses == []
    assert record.current_plan_snapshot is None
    assert record.current_summary_snapshot is None


def test_workspace_record_keeps_local_backend_fields() -> None:
    workspace = WorkspaceRecord(
        workspace_id="workspace-1",
        name="Project Alpha",
        root_path=(
            "E:/Github/AgentHub-weon/backend/.AgentHub/workspaces/workspace-1"
        ),
    )

    assert workspace.backend_type == "local"
    assert workspace.status == "ready"


def test_waiting_item_supports_confirm_and_external_result() -> None:
    confirm_item = WaitingItem(
        waiting_id="wait-1",
        source_type="leader",
        source_runtime_id="leader-runtime",
        waiting_kind="confirm",
        title="Confirm deletion",
        message="Delete foo.py?",
        payload={"path": "foo.py"},
    )
    external_item = WaitingItem(
        waiting_id="wait-2",
        source_type="subagent",
        source_runtime_id="worker-runtime",
        waiting_kind="external_result",
        title="Await tool result",
        message="Waiting for external executor.",
        payload={"tool": "Deploy"},
    )

    assert confirm_item.status == "pending"
    assert external_item.status == "pending"


def test_session_detail_reads_runtime_message_history() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    session = client.post(
        "/api/v1/sessions",
        json={
            "name": "Demo Session",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    response = client.get(f"/api/v1/sessions/{session['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"] == []


def test_session_detail_includes_leader_and_worker_agent_statuses() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    session = client.post(
        "/api/v1/sessions",
        json={
            "name": "Demo Session",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    response = client.get(f"/api/v1/sessions/{session['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    agent_statuses = payload["runtime"]["agent_statuses"]
    agent_ids = [item["agent_id"] for item in agent_statuses]
    assert agent_ids == ["leader-agent", "worker-a", "worker-b"]
