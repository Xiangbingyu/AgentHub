// gateway_service 接入层：所有请求走同源 /api，开发期由 Vite 代理到 gateway。

const API_BASE = '/api';

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`请求失败 ${response.status}: ${text || path}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

// ---- 读 ----
export function listSessions() {
  return fetchJson('/sessions');
}

export function getSessionPage(sessionId) {
  return fetchJson(`/session-page/${sessionId}`);
}

export function listSourceWorkspaces() {
  return fetchJson('/source-workspaces');
}

export function getWorkspacePage(sourceWorkspaceId) {
  return fetchJson(`/workspace-page/${sourceWorkspaceId}`);
}

export function getWorkspaceTree(sourceWorkspaceId, path = '.') {
  const query = new URLSearchParams({ path }).toString();
  return fetchJson(`/source-workspaces/${sourceWorkspaceId}/tree?${query}`);
}

// ---- 写 ----
export function postSessionMessage(sessionId, content) {
  return fetchJson(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function createSession(body) {
  return fetchJson('/sessions', { method: 'POST', body: JSON.stringify(body) });
}

export function createSessionFromSource({ source_workspace_id, title }) {
  return fetchJson('/sessions/from-source', {
    method: 'POST',
    body: JSON.stringify({ source_workspace_id, title }),
  });
}

export function createSourceWorkspace({ name, root_path }) {
  return fetchJson('/source-workspaces', {
    method: 'POST',
    body: JSON.stringify({ name, root_path }),
  });
}

// SSE 流地址（EventSource 直接用，不经 fetch）
export function sessionStreamUrl(sessionId) {
  return `${API_BASE}/sessions/${sessionId}/stream`;
}
