// SSE 流地址（EventSource 直接用，不经 fetch，也不归 RTK Query 管）。
// 其余读写已迁入 src/store/api.js（RTK Query）。
const API_BASE = '/api';

export function sessionStreamUrl(sessionId) {
  return `${API_BASE}/sessions/${sessionId}/stream`;
}
