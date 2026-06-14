from __future__ import annotations

import httpx

from gateway_service.app.config import get_settings


class AgentServiceClient:
    """gateway → agent_service 的 HTTP 客户端。

    每次调用打开一次连接（沿用 agent_service repository 的 per-call 连接风格），
    `_client` 工厂便于测试替换。
    """

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = base_url or get_settings().agent_service_base_url
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self._timeout)

    def _get(self, path: str, params: dict | None = None):
        with self._client() as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    def _post(self, path: str, json: dict | None = None):
        with self._client() as client:
            response = client.post(path, json=json)
            response.raise_for_status()
            return response.json()

    # ---- 读 ----
    def list_session_events(self, session_id: str, since: int = 0) -> list[dict]:
        return self._get(f"/sessions/{session_id}/events", params={"since": since})

    def list_sessions(self) -> list[dict]:
        return self._get("/sessions")

    def get_session(self, session_id: str) -> dict:
        return self._get(f"/sessions/{session_id}")

    def list_session_subtasks(self, session_id: str) -> list[dict]:
        return self._get(f"/sessions/{session_id}/subtasks")

    def list_source_workspaces(self) -> list[dict]:
        return self._get("/source-workspaces")

    def get_source_workspace(self, source_workspace_id: str) -> dict:
        return self._get(f"/source-workspaces/{source_workspace_id}")

    def list_session_workspaces(self, source_workspace_id: str) -> list[dict]:
        return self._get(f"/source-workspaces/{source_workspace_id}/session-workspaces")

    def get_session_workspace(self, session_workspace_id: str) -> dict:
        return self._get(f"/session-workspaces/{session_workspace_id}")

    def get_workspace_tree(self, source_workspace_id: str, path: str = ".") -> list[dict]:
        return self._get(
            f"/source-workspaces/{source_workspace_id}/tree", params={"path": path}
        )

    def get_agent_run(self, run_id: str) -> dict:
        return self._get(f"/agent-runs/{run_id}")

    # ---- 写代理 ----
    def post_message(self, run_id: str, body: dict) -> dict:
        return self._post(f"/agent-runs/{run_id}/input", json=body)

    def post_session_message(self, session_id: str, body: dict) -> dict:
        return self._post(f"/sessions/{session_id}/messages", json=body)

    def create_session(self, body: dict) -> dict:
        return self._post("/sessions", json=body)

    def create_session_from_source(self, body: dict) -> dict:
        return self._post("/sessions/from-source", json=body)

    def delete_session(self, session_id: str) -> dict:
        return self._post(f"/sessions/{session_id}/delete")

    def create_source_workspace(self, body: dict) -> dict:
        return self._post("/source-workspaces", json=body)

    def create_session_workspace(self, body: dict) -> dict:
        return self._post("/session-workspaces", json=body)

    def derive_session_workspace(self, body: dict) -> dict:
        return self._post("/session-workspaces/derive", json=body)

    def create_agent_run(self, body: dict) -> dict:
        return self._post("/agent-runs", json=body)
