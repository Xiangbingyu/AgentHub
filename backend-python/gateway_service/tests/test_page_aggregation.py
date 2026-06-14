import httpx
from fastapi.testclient import TestClient

from gateway_service.app.client.agent_service_client import AgentServiceClient
from gateway_service.app.main import create_app


def _http_404() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://test/x")
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("not found", request=request, response=response)


def test_session_page_projects_events_by_scope(monkeypatch) -> None:
    session = {"session_id": "s1", "session_workspace_id": "sw1", "title": "demo"}
    events = [
        {
            "sequence_no": 1,
            "event_type": "session.message.appended",
            "event_scope": "main_timeline",
            "payload": {"role": "user", "content": "hi"},
        },
        {
            "sequence_no": 2,
            "event_type": "subtask.delegated",
            "event_scope": "subtask_thread",
            "payload": {"subtask_id": "t1"},
        },
        {
            "sequence_no": 3,
            "event_type": "workspace.changed",
            "event_scope": "workspace_panel",
            "payload": {"paths": ["a.py"]},
        },
    ]
    monkeypatch.setattr(AgentServiceClient, "get_session", lambda self, sid: session)
    monkeypatch.setattr(
        AgentServiceClient, "list_session_events", lambda self, sid, since=0: events
    )
    monkeypatch.setattr(
        AgentServiceClient,
        "get_session_workspace",
        lambda self, swid: {"session_workspace_id": swid, "name": "branch-a"},
    )

    client = TestClient(create_app())
    response = client.get("/session-page/s1")

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == "s1"
    assert [e["sequence_no"] for e in body["main_timeline"]] == [1]
    assert [e["sequence_no"] for e in body["subtask_thread"]] == [2]
    assert [e["sequence_no"] for e in body["workspace_panel"]] == [3]
    assert body["session_workspace"]["name"] == "branch-a"


def test_workspace_page_aggregates_source_and_children(monkeypatch) -> None:
    source = {"source_workspace_id": "ws1", "name": "src", "root_path": "E:/x"}
    monkeypatch.setattr(AgentServiceClient, "get_source_workspace", lambda self, wid: source)
    monkeypatch.setattr(
        AgentServiceClient,
        "list_session_workspaces",
        lambda self, wid: [{"session_workspace_id": "sw1", "name": "branch-a"}],
    )
    monkeypatch.setattr(
        AgentServiceClient,
        "get_workspace_tree",
        lambda self, wid, path=".": [{"type": "file", "name": "a.py", "path": "a.py"}],
    )

    client = TestClient(create_app())
    response = client.get("/workspace-page/ws1")

    assert response.status_code == 200
    body = response.json()
    assert body["source_workspace"]["name"] == "src"
    assert len(body["session_workspaces"]) == 1
    assert body["tree"][0]["name"] == "a.py"


def test_session_page_degrades_when_workspace_missing(monkeypatch) -> None:
    session = {"session_id": "s1", "session_workspace_id": "sw-gone", "title": "demo"}
    monkeypatch.setattr(AgentServiceClient, "get_session", lambda self, sid: session)
    monkeypatch.setattr(
        AgentServiceClient, "list_session_events", lambda self, sid, since=0: []
    )

    def _raise(self, swid):
        raise _http_404()

    monkeypatch.setattr(AgentServiceClient, "get_session_workspace", _raise)

    client = TestClient(create_app())
    response = client.get("/session-page/s1")

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == "s1"
    assert body["session_workspace"] is None


def test_workspace_page_degrades_when_tree_missing(monkeypatch) -> None:
    source = {"source_workspace_id": "ws1", "name": "src", "root_path": "E:/missing"}
    monkeypatch.setattr(AgentServiceClient, "get_source_workspace", lambda self, wid: source)
    monkeypatch.setattr(AgentServiceClient, "list_session_workspaces", lambda self, wid: [])

    def _raise(self, wid, path="."):
        raise _http_404()

    monkeypatch.setattr(AgentServiceClient, "get_workspace_tree", _raise)

    client = TestClient(create_app())
    response = client.get("/workspace-page/ws1")

    assert response.status_code == 200
    body = response.json()
    assert body["source_workspace"]["name"] == "src"
    assert body["tree"] == []
