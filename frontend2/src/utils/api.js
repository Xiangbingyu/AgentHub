const API_BASE = 'http://127.0.0.1:8000/api/v1';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let payload;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }
    const message = payload?.error?.message ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  buildSessionStreamUrl(sessionId) {
    return `${API_BASE}/sessions/${sessionId}/stream`;
  },
  listSessions() {
    return request('/sessions');
  },
  getSessionDetail(sessionId) {
    return request(`/sessions/${sessionId}`);
  },
  createSession(payload) {
    return request('/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  sendSessionMessage(sessionId, content) {
    return request(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
  cancelSession(sessionId) {
    return request(`/sessions/${sessionId}/cancel`, {
      method: 'POST',
    });
  },
  resolveWaitingItem(sessionId, waitingId, confirmed) {
    return request(`/sessions/${sessionId}/waiting/${waitingId}`, {
      method: 'POST',
      body: JSON.stringify({ confirmed }),
    });
  },
  listTeams() {
    return request('/teams');
  },
  createTeam(payload) {
    return request('/teams', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listWorkspaces() {
    return request('/workspaces');
  },
  createWorkspace(payload) {
    return request('/workspaces', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getWorkspaceTree(workspaceId, path = '') {
    const search = new URLSearchParams();
    if (path) search.set('path', path);
    const suffix = search.toString() ? `?${search.toString()}` : '';
    return request(`/workspaces/${workspaceId}/tree${suffix}`);
  },
  getWorkspaceFile(workspaceId, path) {
    const search = new URLSearchParams({ path });
    return request(`/workspaces/${workspaceId}/files?${search.toString()}`);
  },
};
