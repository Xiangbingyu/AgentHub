import { useCallback, useMemo, useRef, useState } from 'react';
import SessionList from '../../components/SessionList/SessionList';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import RuntimePanel from '../../components/RuntimePanel/RuntimePanel';
import Modal from '../../components/Modal/Modal';
import useSessionStream from '../../hooks/useSessionStream';
import {
  useListSessionsQuery,
  useGetSessionPageQuery,
  useListSourceWorkspacesQuery,
  usePostSessionMessageMutation,
  useCreateSessionFromSourceMutation,
} from '../../store/api';
import './Chat.css';

const RUNTIME_PANEL_DEFAULT_WIDTH = 360;
const RUNTIME_PANEL_MIN_WIDTH = 280;
const RUNTIME_PANEL_MAX_WIDTH = 560;
const CENTER_PANEL_MIN_WIDTH = 480;
const RUNTIME_COLLAPSED_WIDTH = 44;

function roleToAuthor(role) {
  return role === 'user' ? '你' : 'Agent';
}

// 后端 main_timeline 事件 → ChatPanel 消息形状
function eventToMessage(event) {
  // 用户消息 payload.role === 'user'；agent 回复为 'assistant'（或缺省按 agent 处理）
  const role = event.payload?.role === 'user' ? 'user' : 'agent';
  return {
    message_id: `evt-${event.sequence_no}`,
    sequence_no: event.sequence_no,
    role,
    author: event.payload?.author || roleToAuthor(role),
    content: event.payload?.content ?? '',
  };
}

export default function Chat() {
  // 用户显式选中的 session；未选时回退到列表第一条（派生，不存 state）
  const [selectedSessionId, setSelectedSessionId] = useState('');
  // SSE 实时回流的消息缓冲（与 query 历史合并），切 session 时清空
  const [liveBuffer, setLiveBuffer] = useState([]);
  // agent 运行态：由 SSE 的 run.started / run.completed 驱动
  const [agentRunning, setAgentRunning] = useState(false);
  const [bufferedSessionId, setBufferedSessionId] = useState('');
  const [runtimeWidth, setRuntimeWidth] = useState(RUNTIME_PANEL_DEFAULT_WIDTH);
  const [runtimeCollapsed, setRuntimeCollapsed] = useState(false);
  const containerRef = useRef(null);

  // 建 session 弹窗状态
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newSourceId, setNewSourceId] = useState('');
  const [createError, setCreateError] = useState('');

  // 会话列表：缓存命中立即渲染，后台 refetch
  const { data: sessions = [] } = useListSessionsQuery();
  // 建 session 弹窗打开时才拉 source 列表
  const { data: sources = [] } = useListSourceWorkspacesQuery(undefined, { skip: !createOpen });

  const activeSessionId = selectedSessionId || sessions[0]?.session_id || '';

  // 选中 session 的历史 + workspace 快照
  const { data: sessionPage } = useGetSessionPageQuery(activeSessionId, {
    skip: !activeSessionId,
  });

  const [postMessage] = usePostSessionMessageMutation();
  const [createSession, { isLoading: creating }] = useCreateSessionFromSourceMutation();

  // 切换 session 时清空上一会话的实时缓冲（渲染期同步，避免 effect 级联）
  if (bufferedSessionId !== activeSessionId) {
    setBufferedSessionId(activeSessionId);
    setLiveBuffer([]);
    setAgentRunning(false);
  }

  // 弹窗的默认 source 选择（派生：未选则取第一条）
  const effectiveSourceId = newSourceId || sources[0]?.source_workspace_id || '';

  function openCreateModal() {
    setCreateError('');
    setNewTitle('');
    setNewSourceId('');
    setCreateOpen(true);
  }

  function handleCreateSession() {
    if (!effectiveSourceId || !newTitle.trim()) {
      setCreateError('请填写标题并选择一个 source workspace');
      return;
    }
    setCreateError('');
    createSession({ source_workspace_id: effectiveSourceId, title: newTitle.trim() })
      .unwrap()
      .then((session) => {
        setCreateOpen(false);
        setSelectedSessionId(session.session_id);
      })
      .catch((err) => setCreateError(err?.data?.detail || err?.error || '创建失败'));
  }

  const sessionWorkspace = sessionPage?.session_workspace ?? null;

  // 历史消息（来自 query）与实时缓冲（来自 SSE / 乐观回显）合并、去重、排序。
  // - 真实事件带正整数 sequence_no；乐观项 optimistic=true 且无 sequence_no。
  // - 真实用户消息到达后，丢弃 content 相同的乐观项，避免重复。
  const messages = useMemo(() => {
    const history = (sessionPage?.main_timeline ?? [])
      .filter((event) => event.event_type === 'session.message.appended')
      .map(eventToMessage);

    const real = [...history];
    const seenSeq = new Set(history.map((m) => m.sequence_no));
    const liveReal = [];
    const liveOptimistic = [];
    for (const m of liveBuffer) {
      if (m.optimistic) {
        liveOptimistic.push(m);
      } else if (!seenSeq.has(m.sequence_no)) {
        liveReal.push(m);
        seenSeq.add(m.sequence_no);
      }
    }
    real.push(...liveReal);
    real.sort((a, b) => (a.sequence_no ?? 0) - (b.sequence_no ?? 0));

    // 已被真实用户事件覆盖的乐观项剔除
    const realUserContents = new Set(
      real.filter((m) => m.role === 'user').map((m) => m.content),
    );
    const pendingOptimistic = liveOptimistic.filter(
      (m) => !realUserContents.has(m.content),
    );

    return [...real, ...pendingOptimistic];
  }, [sessionPage, liveBuffer]);

  // SSE 实时：消息事件进缓冲；run 生命周期事件驱动 agent 运行态。
  const handleStreamEvent = useCallback((event) => {
    if (event.event_type === 'run.started') {
      setAgentRunning(true);
      return;
    }
    if (event.event_type === 'run.completed') {
      setAgentRunning(false);
      return;
    }
    if (event.event_type !== 'session.message.appended') {
      return;
    }
    const incoming = eventToMessage(event);
    // agent 回复到达即视为本轮结束（run.completed 可能稍后才到）
    if (incoming.role === 'agent') {
      setAgentRunning(false);
    }
    setLiveBuffer((current) => {
      if (current.some((m) => m.sequence_no === incoming.sequence_no)) {
        return current;
      }
      return [...current, incoming];
    });
  }, []);

  useSessionStream(activeSessionId, handleStreamEvent);

  function handleSendMessage(content) {
    if (!activeSessionId) {
      return;
    }
    // 乐观回显：立即把用户消息推入缓冲（不带 pending，光标不挂在用户气泡上）
    setLiveBuffer((current) => [
      ...current,
      {
        message_id: `optimistic-${current.length}-${content.length}`,
        sequence_no: null,
        role: 'user',
        author: '你',
        content,
        optimistic: true,
      },
    ]);
    // 立即进入运行态，等 SSE 的 run.started/回复再校正
    setAgentRunning(true);
    // agent 回复经 SSE 回流追加；真实用户事件回流后会顶替上面的乐观项
    postMessage({ sessionId: activeSessionId, content }).unwrap().catch(() => undefined);
  }

  const activeSession =
    sessions.find((session) => session.session_id === activeSessionId) ?? null;

  const runtime = activeSession
    ? {
        session_title: activeSession.title,
        session_status: activeSession.status,
        session_workspace: sessionWorkspace?.name ?? '—',
        source_workspace: sessionWorkspace?.source_workspace_id ?? '—',
        agent_status: agentRunning ? 'running' : 'idle',
        task_status: '—',
        plan_steps: 0,
      }
    : null;

  function clampWidth(value, min, max) {
    const safeMax = Math.max(min, max);
    return Math.min(Math.max(value, min), safeMax);
  }

  function startResize(event) {
    event.preventDefault();
    const container = containerRef.current;
    if (!container || runtimeCollapsed) {
      return;
    }
    const rect = container.getBoundingClientRect();

    function handleMouseMove(moveEvent) {
      const nextWidth = clampWidth(
        rect.right - moveEvent.clientX,
        RUNTIME_PANEL_MIN_WIDTH,
        Math.min(RUNTIME_PANEL_MAX_WIDTH, rect.width - CENTER_PANEL_MIN_WIDTH),
      );
      setRuntimeWidth(nextWidth);
    }

    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('is-resizing-panels');
    }

    document.body.classList.add('is-resizing-panels');
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }

  return (
    <div className="chat-page" ref={containerRef}>
      <SessionList
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setSelectedSessionId}
        onCreateSession={openCreateModal}
      />
      <div className="chat-page-center">
        <ChatPanel
          session={activeSession}
          messages={messages}
          onSendMessage={handleSendMessage}
          sending={agentRunning}
          agentTyping={agentRunning}
        />
      </div>
      <div
        className={`chat-page-runtime ${runtimeCollapsed ? 'collapsed' : ''}`}
        style={{ width: `${runtimeCollapsed ? RUNTIME_COLLAPSED_WIDTH : runtimeWidth}px` }}
      >
        {!runtimeCollapsed ? (
          <button
            type="button"
            className="panel-resize-handle"
            aria-label="调整运行态宽度"
            onMouseDown={startResize}
          />
        ) : null}
        <RuntimePanel
          runtime={runtime}
          collapsed={runtimeCollapsed}
          onToggleCollapse={() => setRuntimeCollapsed((current) => !current)}
        />
      </div>

      <Modal open={createOpen} title="新建 Session" onClose={() => setCreateOpen(false)}>
        {createError ? <div className="modal-error">{createError}</div> : null}
        <div className="modal-field">
          <label htmlFor="new-session-title">会话标题</label>
          <input
            id="new-session-title"
            type="text"
            value={newTitle}
            placeholder="例如：重构登录模块"
            onChange={(event) => setNewTitle(event.target.value)}
          />
        </div>
        <div className="modal-field">
          <label htmlFor="new-session-source">Source Workspace（将自动派生隔离副本）</label>
          <select
            id="new-session-source"
            value={effectiveSourceId}
            onChange={(event) => setNewSourceId(event.target.value)}
          >
            {sources.length === 0 ? <option value="">（暂无，请先在 Workspace 页创建）</option> : null}
            {sources.map((source) => (
              <option key={source.source_workspace_id} value={source.source_workspace_id}>
                {source.name}
              </option>
            ))}
          </select>
        </div>
        <div className="modal-actions">
          <button type="button" className="modal-btn" onClick={() => setCreateOpen(false)}>
            取消
          </button>
          <button
            type="button"
            className="modal-btn primary"
            disabled={creating}
            onClick={handleCreateSession}
          >
            {creating ? '创建中…' : '创建'}
          </button>
        </div>
      </Modal>
    </div>
  );
}
