from gateway_service.app.client.agent_service_client import AgentServiceClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, captured):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        self._captured["method"] = "GET"
        self._captured["url"] = url
        self._captured["params"] = params
        return _FakeResponse(self._captured.get("get_payload", []))

    def post(self, url, json=None):
        self._captured["method"] = "POST"
        self._captured["url"] = url
        self._captured["json"] = json
        return _FakeResponse(self._captured.get("post_payload", {}))


def _patch_client(monkeypatch, captured):
    def _factory(self):
        return _FakeClient(captured)

    monkeypatch.setattr(AgentServiceClient, "_client", _factory)


def test_list_session_events_calls_correct_url(monkeypatch) -> None:
    captured = {"get_payload": [{"sequence_no": 2, "event_type": "x", "payload": {}}]}
    _patch_client(monkeypatch, captured)

    client = AgentServiceClient(base_url="http://agent:8000")
    result = client.list_session_events("sid-1", since=3)

    assert captured["method"] == "GET"
    assert captured["url"] == "/sessions/sid-1/events"
    assert captured["params"] == {"since": 3}
    assert result == captured["get_payload"]


def test_get_source_workspace_tree_passes_path(monkeypatch) -> None:
    captured = {"get_payload": []}
    _patch_client(monkeypatch, captured)

    client = AgentServiceClient(base_url="http://agent:8000")
    client.get_workspace_tree("ws-1", path="src")

    assert captured["url"] == "/source-workspaces/ws-1/tree"
    assert captured["params"] == {"path": "src"}


def test_post_message_proxies_payload(monkeypatch) -> None:
    captured = {"post_payload": {"run_id": "r1", "status": "accepted"}}
    _patch_client(monkeypatch, captured)

    client = AgentServiceClient(base_url="http://agent:8000")
    body = {"input_id": "i1", "type": "user_input", "payload": {"content": "hi"}}
    result = client.post_message("run-1", body)

    assert captured["method"] == "POST"
    assert captured["url"] == "/agent-runs/run-1/input"
    assert captured["json"] == body
    assert result == captured["post_payload"]


def test_default_base_url_from_settings(monkeypatch) -> None:
    client = AgentServiceClient()
    assert client.base_url.startswith("http")


def test_client_reuses_shared_httpx_client() -> None:
    client = AgentServiceClient(base_url="http://agent:8000")

    first = client._client()
    second = client._client()

    assert first is second
